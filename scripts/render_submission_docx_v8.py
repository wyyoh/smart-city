"""Use the packaged DOCX renderer with Microsoft Word conversion on Windows.

The bundled renderer needs LibreOffice, which is not installed on this host.
Only its conversion callback is adapted; the managed skill files are unchanged.
"""
import argparse
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--renderer', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('packaged_docx_renderer', args.renderer)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def convert(doc_path, user_profile, output_dir, stem, verbose=False):
        output = Path(output_dir)/(stem+'.pdf')
        # Values are single-quoted PowerShell literals, never shell substitutions.
        literal = lambda value: "'"+str(value).replace("'", "''")+"'"
        script = "$word=New-Object -ComObject Word.Application; try { $word.Visible=$false; $word.DisplayAlerts=0; "
        script += '$doc=$word.Documents.Open('+literal(Path(doc_path).resolve())+',$false,$true); '
        script += 'try { $doc.ExportAsFixedFormat('+literal(output.resolve())+',17) } finally { $doc.Close(0) } '
        script += '} finally { $word.Quit(); [Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null }'
        completed = subprocess.run(['powershell.exe', '-NoProfile', '-Command', script],
                                   capture_output=True, text=True, encoding='utf-8', timeout=120,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        if completed.returncode or not output.exists():
            raise RuntimeError(completed.stderr or 'Word did not produce the PDF')
        return str(output), 'Converted by installed Microsoft Word; packaged PNG rasterization retained.'

    module.convert_to_pdf = convert
    sys.argv = [str(args.renderer), str(args.input), '--output_dir', str(args.output_dir), '--emit_pdf']
    module.main()


if __name__ == '__main__':
    main()
