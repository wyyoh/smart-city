"""Scientific figures and process schematics for the work paper."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle
import numpy as np


def build_figures(data, out):
    out.mkdir(parents=True, exist_ok=True)
    font=font_manager.FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
    font_manager.fontManager.addfont('C:/Windows/Fonts/msyh.ttc')
    plt.rcParams.update({'font.family':font.get_name(), 'font.size':10,
                         'axes.unicode_minus':False, 'svg.fonttype':'none'})
    ink='#173F3B'; teal='#177F76'; pale='#EDF3EF'; grey='#56645F'
    figures={}
    def save(key, fig, caption, source='资料来源：本作品的结构设计与已保存案例。'):
        path=out/(key+'.png')
        fig.savefig(path,dpi=220,bbox_inches='tight',facecolor='white')
        plt.close(fig)
        figures[key]={'path':str(path),'caption':caption,'source':source}
    def flow(key, labels, caption, width=8.8):
        fig,ax=plt.subplots(figsize=(width,1.6))
        n=len(labels)
        ax.set_xlim(0,n*2.25); ax.set_ylim(.4,1.7)
        for i,label in enumerate(labels):
            x=.12+i*2.25
            ax.add_patch(Rectangle((x,.65),1.86,.82,facecolor=pale,edgecolor=ink,lw=.8))
            ax.text(x+.93,1.06,label,ha='center',va='center',fontsize=11.5,color=ink)
            if i<n-1:
                ax.annotate('',xy=(x+2.23,1.06),xytext=(x+1.87,1.06),
                            arrowprops={'arrowstyle':'->','lw':1,'color':grey})
        ax.axis('off'); save(key,fig,caption)
    flow('workflow',['场景与要求\n确认依据','历史材料\n逐项筛选','可行候选\n比较取舍','准确父配方\n继续设计'],
         '工程师从需求确认进入材料比较与后续设计')
    flow('requirements',['场景字段\n项目输入','规则命中\n出处与条件','工程师确认\n记录覆盖理由','需求版本\n绑定本次决策'],
         '场景规则与人工确认形成有来源的需求')
    flow('design-lineage',['确认需求\n场景与目标','材料决策\n准确父配方','组成探索\n变量与锁定项','设计草案\n改动与原需求'],
         '需求与父配方在设计过程中的关联')
    flow('architecture',['React界面\n案例与设计','FastAPI服务\n需求 决策 研究','SQLite记录\n材料与过程','导出与接口\nJSON OpenAPI'],
         '原型的主要模块与数据交接')
    flow('validation-flow',['来源分组\n共同划分','外层训练\n内部三折选参','外层测试\n计算目标误差','五次分组重复\n汇总并核对样本'],
         '性能研究中的分组与嵌套评估过程')
    fig,ax=plt.subplots(figsize=(8,3.4)); ax.axis('off'); ax.set_xlim(0,10); ax.set_ylim(0,4)
    boxes=[(.3,1.5,3,1,'固定数值可行集合\nH J R7 V K'),
           (5,2.4,4.4,.9,'TSR优先：先看H'),
           (5,.8,4.4,.9,'残留稳定度优先：先看K')]
    for x,y,w,h,label in boxes:
        ax.add_patch(Rectangle((x,y),w,h,facecolor=pale,edgecolor=ink,lw=.8))
        ax.text(x+w/2,y+h/2,label,ha='center',va='center',fontsize=11,color=ink)
    for y in [2.85,1.25]:
        ax.annotate('',xy=(5,y),xytext=(3.3,2),arrowprops={'arrowstyle':'->','lw':1,'color':grey})
    ax.text(5,.25,'两种顺序均保留原5项候选',fontsize=10,color=grey)
    save('preferences',fig,'C3在同一可行集合中切换优先指标')
    fig,ax=plt.subplots(figsize=(8,3.6)); ax.axis('off'); ax.set_xlim(0,10); ax.set_ylim(0,4)
    for x,y,w,h,label in [
        (.2,1.5,2.6,1,'空结果\n读取当前范围'),
        (3.8,2.65,5.8,.9,'尚有未被已知失败排除的候选\n组织待补资料'),
        (3.8,.6,5.8,.9,'数值完整的选定范围\n核对冲突子集与见证')]:
        ax.add_patch(Rectangle((x,y),w,h,facecolor=pale,edgecolor=ink,lw=.8))
        ax.text(x+w/2,y+h/2,label,ha='center',va='center',fontsize=10,color=ink)
    for y in [3.1,1.05]:
        ax.annotate('',xy=(3.8,y),xytext=(2.8,2),arrowprops={'arrowstyle':'->','lw':1,'color':grey})
    save('diagnosis',fig,'空结果依据已知失败与资料状态分别解释')
    c3=data['cases'][2]['candidates']
    fig,ax=plt.subplots(figsize=(7.8,4.4))
    for row in c3:
        x=row['values']['TSR'];y=row['values']['residual']
        ax.scatter([x],[y],s=65,color=teal)
        label=row['source'] if row['display_id']!='R7' else '1L / R7'
        ax.annotate(label,(x,y),xytext=(7,7),textcoords='offset points',fontsize=10)
    ax.axvline(85,color='#B77736',ls='--',lw=1)
    ax.axhline(90,color='#B77736',ls='--',lw=1)
    ax.set(xlim=(84,94.3),ylim=(89.7,95.6),xlabel='冻融劈裂比 TSR / %',ylabel='残留稳定度 / %')
    ax.grid(alpha=.18); ax.spines[['top','right']].set_visible(False)
    save('pareto',fig,'C3候选在TSR与残留稳定度上的历史值',
         '资料来源：C3快照。虚线为本案要求；四指标非支配关系另由完整数据计算。')
    c1=data['cases'][0]
    fig,axes=plt.subplots(2,2,figsize=(8,5.3),layout='constrained')
    for ax,metric,name,unit in zip(axes.flat,['DS','strain','TSR','residual'],
        ['动稳定度','应变','TSR','残留稳定度'],['次/mm','με','%','%']):
        vals=[r['values'][metric] for r in c1['candidates']]
        target=next(t['value'] for t in c1['targets'] if t['metric']==metric)
        ax.barh(['H','S'],vals,color=[teal,'#587CA0'],height=.5)
        ax.axvline(target,color='#B77736',ls='--',lw=1)
        ax.set_xlabel(name+' / '+unit,fontsize=9)
        ax.set_xlim(0,max(vals+[target])*1.25)
        for i,v in enumerate(vals): ax.text(v+max(vals)*.025,i,f'{v:.2f}',va='center',fontsize=9)
        ax.spines[['top','right']].set_visible(False)
    save('c1-margins',fig,'C1两个候选与各项要求的比较',
         '资料来源：C1快照。虚线为对应指标要求值，四图分别使用原单位。')
    fig,ax=plt.subplots(figsize=(7.8,3.5))
    ax.barh(['父配方','设计假设'],[4.9,5.0],color=[grey,teal],height=.48)
    ax.set_xlim(0,6); ax.set_xlabel('油石比 / %')
    for i,v in enumerate([4.9,5.0]): ax.text(v+.08,i,f'{v:.1f}%',va='center')
    ax.text(.2,1.5,'本次增加0.1个百分点；组分名义份额保持固定',fontsize=10)
    ax.spines[['top','right']].set_visible(False)
    save('c2-change',fig,'C2父配方与设计假设的油石比',
         '资料来源：C2设计草案。图中展示组成变量的实际改动。')
    fig,ax=plt.subplots(figsize=(8,3.8)); ax.axis('off'); ax.set_xlim(0,10);ax.set_ylim(0,4)
    for x,label in [(.2,'84条AC-13目录\n44条已知失败\n40条待补证据'),
                    (6,'35条完整数值子池\n35条已知失败\n4组最小冲突')]:
        ax.add_patch(Rectangle((x,.9),3.7,2.2,facecolor=pale,edgecolor=ink,lw=.8))
        ax.text(x+1.85,2,label,ha='center',va='center',fontsize=11,color=ink,linespacing=1.8)
    ax.annotate('',xy=(6,2),xytext=(3.9,2),arrowprops={'arrowstyle':'->','color':grey,'lw':1})
    ax.text(4.95,2.5,'工程师明确\n选择子池',ha='center',fontsize=9)
    save('c5-scopes',fig,'C5的目录范围与完整数值诊断范围',
         '资料来源：C5及C5完整数值子池快照。范围与结论同时保存。')
    r=data['research']; base=np.array(r['mean_baseline_mae'])
    old=np.array(r['original_pipeline_mae'])/base*100
    new=np.array(r['conservative_ensemble_mae'])/base*100
    fig,ax=plt.subplots(figsize=(8,4.1))
    x=np.arange(4); w=.34
    ax.bar(x-w/2,old,width=w,color='#758891',label='原选模流程')
    ax.bar(x+w/2,new,width=w,color=teal,label='保守集成')
    ax.axhline(100,color='#B77736',ls='--',lw=1,label='同划分均值基准')
    ax.set(xticks=x,xticklabels=['DS','应变','TSR','残留稳定度'],
           ylabel='相对MAE（均值基准=100）',ylim=(0,125))
    for i in range(4):
        ax.text(i-w/2,old[i]+1.4,f'{old[i]:.2f}',ha='center',fontsize=9)
        ax.text(i+w/2,new[i]+1.4,f'{new[i]:.2f}',ha='center',fontsize=9)
    ax.legend(frameon=False,ncol=3,loc='upper center',bbox_to_anchor=(.5,-.13),fontsize=9)
    ax.spines[['top','right']].set_visible(False)
    save('model-errors',fig,'各项MAE相对于同划分均值基准的位置',
         '资料来源：既有模型计算结果。相对值按未舍入MAE计算；数值越低表示误差越小。')
    return figures
