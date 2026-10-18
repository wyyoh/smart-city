import re
import socket
from unittest.mock import patch


def test_offline_core_and_local_assets(client):
    def no_external(*args,**kwargs):
        raise AssertionError('核心运行发生了外部网络访问')
    with patch.object(socket,'create_connection',no_external),patch.object(socket.socket,'connect',no_external):
        page=client.get('/')
        assert page.status_code==200
        paths=re.findall(r'(?:src|href)="([^"]+)"',page.text)
        for path in paths:
            assert path.startswith('/') and not path.startswith('//')
            assert client.get(path).status_code==200
        scenario=client.get('/v1/cases').json()[0]['scenario']
        result=client.post('/v1/recommendations',json=scenario)
        assert result.status_code==201
        report=client.get('/v1/recommendations/'+result.json()['id']+'/report.html')
        assert report.status_code==200
        assert 'https://' not in report.text
