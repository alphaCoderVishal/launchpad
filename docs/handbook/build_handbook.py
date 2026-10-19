"""Build the source-checked Launchpad learning handbook as a vector PDF.

Run with the Codex bundled Python runtime. No application code is modified.
"""
from pathlib import Path
import math
import re
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.utils import ImageReader

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = HERE / 'Launchpad_Project_and_Interview_Handbook.pdf'
FONT_DIR = Path('C:/Windows/Fonts')
for name, filename in [('UI','segoeui.ttf'),('UI-Bold','segoeuib.ttf'),('UI-Italic','segoeuii.ttf'),('Mono','consola.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / filename)))
pdfmetrics.registerFontFamily('UI',normal='UI',bold='UI-Bold',italic='UI-Italic',boldItalic='UI-Bold')
INK=colors.HexColor('#152238'); MUTED=colors.HexColor('#59677A'); TEAL=colors.HexColor('#087F83')
BLUE=colors.HexColor('#234A70'); PALE=colors.HexColor('#EAF4F4'); LINE=colors.HexColor('#D9D9D9')
AMBER=colors.HexColor('#A66317'); RED=colors.HexColor('#A63E47'); WHITE=colors.white
W,H=595.276,841.89; LEFT=48; CW=W-96; BOTTOM=54
BODY=ParagraphStyle('body',fontName='UI',fontSize=10.6,leading=15,textColor=INK,spaceAfter=9)
SMALL=ParagraphStyle('small',parent=BODY,fontSize=9.2,leading=12.6,textColor=MUTED)
HEAD=ParagraphStyle('head',fontName='UI-Bold',fontSize=23,leading=28,textColor=colors.black)
SUB=ParagraphStyle('sub',fontName='UI-Bold',fontSize=12.2,leading=16.8,textColor=colors.black)
CELL=ParagraphStyle('cell',fontName='UI',fontSize=9.1,leading=12.5,textColor=INK)
CELLHEAD=ParagraphStyle('cellhead',parent=CELL,fontName='UI-Bold',textColor=WHITE)
CAPTION=ParagraphStyle('caption',parent=SMALL,fontSize=9,leading=12)

class Page:
    def __init__(self,c,number,title,part='Understand the implementation'):
        self.c=c; self.number=number; self.y=H-48
        c.bookmarkPage(f'p{number}'); c.addOutlineEntry(title,f'p{number}',0)
        c.setFillColor(colors.black); c.setFont('UI',8.4); c.drawString(LEFT,self.y,'LAUNCHPAD  /  '+part.upper())
        self.y-=32
        self.p(title,HEAD,12)
    def need(self,height):
        if self.y-height < BOTTOM:
            raise ValueError(f'Page {self.number} overflows by {BOTTOM-(self.y-height):.1f} pt at y={self.y:.1f}')
    def p(self,text,style=BODY,gap=8):
        para=Paragraph(text,style); _,height=para.wrap(CW,900)
        self.need(height+gap); para.drawOn(self.c,LEFT,self.y-height); self.y-=height+gap
    def h(self,text): self.p(text,SUB,7)
    def table(self,headers,rows,widths=None):
        data=[[Paragraph(str(x),CELLHEAD) for x in headers]]
        data += [[Paragraph(str(x),CELL) for x in row] for row in rows]
        widths=[CW*x for x in widths] if widths else [CW/len(headers)]*len(headers)
        t=Table(data,colWidths=widths,hAlign='LEFT',repeatRows=1)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),BLUE),('GRID',(0,0),(-1,-1),.5,LINE),
          ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,colors.HexColor('#F3F6F8')]),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
          ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
          ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
        _,height=t.wrap(CW,900); self.need(height+13); t.drawOn(self.c,LEFT,self.y-height); self.y-=height+13
    def code(self,text):
        lines=text.strip('\n').splitlines(); leading=12.4; height=len(lines)*leading+15
        self.need(height+10); self.c.setFillColor(colors.HexColor('#F1F4F7')); self.c.rect(LEFT,self.y-height,CW,height,fill=1,stroke=0)
        self.c.setFont('Mono',8.4); self.c.setFillColor(INK)
        for i,line in enumerate(lines):
            if pdfmetrics.stringWidth(line,'Mono',8.4)>CW-20: raise ValueError('Code line too wide: '+line)
            self.c.drawString(LEFT+10,self.y-14-i*leading,line)
        self.y-=height+10
    def figure(self,kind,height,caption):
        self.need(height+34); self.c.saveState(); self.c.translate(LEFT,self.y-height)
        draw_diagram(self.c,kind,CW,height); self.c.restoreState(); self.y-=height+4
        self.p(caption,CAPTION,11)
    def image(self,path,caption,width=CW):
        img=ImageReader(str(ROOT/path)); iw,ih=img.getSize(); height=width*ih/iw
        self.need(height+37); self.c.drawImage(img,LEFT+(CW-width)/2,self.y-height,width,height,mask='auto'); self.y-=height+5
        self.p(caption,CAPTION,13)
    def finish(self):
        self.c.setFont('UI',8); self.c.setFillColor(MUTED)
        self.c.drawString(LEFT,30,'Project understanding and interview preparation  |  20 October 2026')
        self.c.drawRightString(W-LEFT,30,f'{self.number:02d} / 32')
        self.c.showPage()

def draw_diagram(c,kind,width,height):
    def text(x,y,w,h,s,size=9.4,color=INK,bold=False,align=TA_CENTER):
        st=ParagraphStyle('diagram',fontName='UI-Bold' if bold else 'UI',fontSize=size,leading=size*1.3,textColor=color,alignment=align)
        p=Paragraph(s,st); _,ph=p.wrap(w,h+100)
        if ph>h+1: raise ValueError(f'Diagram text overflow {kind}: {s}')
        p.drawOn(c,x,height-y-(h+ph)/2)
    def box(x,y,w,h,title,detail='',fill=PALE,stroke=TEAL):
        c.setFillColor(fill); c.setStrokeColor(stroke); c.setLineWidth(.8)
        c.roundRect(x,height-y-h,w,h,7,fill=1,stroke=1)
        col=WHITE if fill in (INK,BLUE,TEAL) else INK
        if detail:
            text(x+7,y+7,w-14,19,title,10,col,True)
            text(x+7,y+28,w-14,h-33,detail,8.9,col)
        else: text(x+6,y+4,w-12,h-8,title,9.7,col,True)
    def arrow(x1,y1,x2,y2,label='',dashed=False,color=BLUE):
        c.setStrokeColor(color); c.setFillColor(color); c.setLineWidth(1.1)
        c.setDash(3,3) if dashed else c.setDash()
        c.line(x1,height-y1,x2,height-y2); c.setDash()
        a=math.atan2(-(y2-y1),x2-x1); size=5
        p=c.beginPath(); p.moveTo(x2,height-y2)
        p.lineTo(x2-size*math.cos(a-.45),height-y2-size*math.sin(a-.45)); p.lineTo(x2-size*math.cos(a+.45),height-y2-size*math.sin(a+.45)); p.close()
        c.drawPath(p,fill=1,stroke=0)
        if label: text((x1+x2)/2-75,(y1+y2)/2-22,150,18,label,8.2)
    if kind in ('cover','overview'):
        box(0,8,132,65,'Developer','Dashboard or REST client')
        box(180,8,145,65,'Spring control plane','Security, validation, lifecycle API',BLUE,BLUE)
        box(370,8,127,65,'Durable database','Intent, active route and audit')
        arrow(132,40,180,40); arrow(325,40,370,40)
        box(180,121,145,63,'Single worker','Replay durable pending work',BLUE,BLUE)
        arrow(430,73,325,144,'worker polls')
        box(0,215,139,64,'Last promoted target','Current workload response')
        box(180,215,145,64,'Docker engine','Fixed image and argument list')
        box(368,215,129,64,'Candidate workload','HTTP health gate')
        arrow(252,184,252,215); arrow(325,248,368,248)
        arrow(180,60,70,215,'active response proxy',dashed=True)
        text(7,299,480,25,'SQL transaction boundaries cover durable state; Docker is reconciled separately.',9.3)
    elif kind=='sequence':
        xs=[38,143,252,361,462]; names=['Client','API','Database','Worker','Docker']
        for x,name in zip(xs,names):
            box(x-33,0,66,30,name)
            c.setStrokeColor(LINE); c.line(x,height-35,x,12)
        events=[(0,1,58,'POST intent + key'),(1,2,92,'Tx A  lock and persist'),(1,0,125,'202 + deployment ID'),
          (3,2,164,'read QUEUED and claim'),(3,4,203,'ensure candidate'),(3,4,240,'three healthy probes'),
          (3,2,278,'Tx B  promote + SUCCEEDED'),(0,1,316,'GET current status')]
        for a,b,y,label in events: arrow(xs[a],y,xs[b],y,label)
    elif kind=='states':
        box(0,15,140,43,'WAITING_APPROVAL'); box(181,15,117,43,'QUEUED'); box(347,15,150,43,'DEPLOYING')
        arrow(140,36,181,36,'operator'); arrow(298,36,347,36,'worker')
        box(0,120,140,43,'CANCELLED',fill=colors.HexColor('#F2F3F5'),stroke=MUTED)
        arrow(70,58,70,120); arrow(215,58,140,139,dashed=True)
        box(178,120,130,43,'SUCCEEDED'); box(347,120,130,43,'ROLLED_BACK')
        arrow(400,58,244,120,'healthy'); arrow(422,58,422,120,'failure + prior target')
        box(347,198,130,43,'FAILED',fill=colors.HexColor('#FFF2EC'),stroke=AMBER)
        # Route failure around terminal nodes, never through ROLLED_BACK.
        c.setStrokeColor(BLUE); c.setLineWidth(1.1); c.setDash(3,3)
        c.line(490,height-58,490,height-220); c.setDash()
        arrow(490,220,477,220,dashed=True)
        text(2,193,306,45,'DEPLOYING can be replayed after restart.<br/>CLEANED is an audit event, not a state.',9.5)
    elif kind=='erd':
        box(0,5,145,131,'services','PK name<br/>owner<br/>active_release<br/>active_container<br/>active_port')
        box(180,5,153,176,'deployments','PK id<br/>FK service_name<br/>release_name and environment<br/>requested_by + request_key<br/>status and detail<br/>candidate_container',BLUE,BLUE)
        box(368,5,129,131,'audit_events','PK id<br/>FK deployment_id<br/>actor and event_type<br/>detail and timestamp')
        arrow(145,66,180,66); arrow(333,66,368,66)
        text(145,43,35,15,'1:N',8.3); text(333,43,35,15,'1:N',8.3)
        box(0,164,145,48,'quota_lock','One shared lock row')
        text(177,190,320,28,'Unique constraint on requested_by and request_key',9.1)
    elif kind=='idempotency':
        box(0,16,137,53,'Lock service row','One intent at a time')
        box(181,16,135,53,'Look up actor + key','Persisted request scope')
        box(360,16,137,53,'Same intent','Replay original UUID')
        arrow(137,43,181,43); arrow(316,43,360,43)
        text(316,21,44,16,'match',8.2)
        box(181,118,135,53,'No prior key','Check busy state and insert')
        box(360,118,137,53,'Different intent','409 conflict',fill=colors.HexColor('#FFF2EC'),stroke=AMBER)
        arrow(248,69,248,118,'not found'); arrow(316,60,360,118)
        text(365,82,80,16,'mismatch',8.2)
    elif kind=='locking':
        for i,(name,detail) in enumerate([('Request A','Acquires service row lock'),('Request B','Waits for A to commit'),('After commit','B sees replay or busy state')]):
            box(i*171,15,155,70,name,detail,BLUE if i==0 else PALE,BLUE if i==0 else TEAL)
        arrow(155,50,171,50); arrow(326,50,342,50)
        text(0,106,497,27,'The Java synchronized worker protects one JVM; the database lock protects request races.',9.3)
    elif kind=='health':
        values=[('200','1',TEAL),('503','0',RED),('200','1',TEAL),('200','2',TEAL),('200','3',TEAL)]
        for i,(http,count,color) in enumerate(values):
            x=i*101; box(x,9,92,61,'HTTP '+http,'Healthy streak = '+count,PALE,color)
            if i<4: arrow(x+92,40,x+101,40)
        text(0,90,497,32,'Illustrative probe sequence  A failure resets the streak; the fifth response permits promotion.',9.3)
    elif kind=='rollback':
        box(0,4,149,55,'Active route','points to v1',BLUE,BLUE)
        box(349,4,148,55,'Workload v1','continues serving')
        arrow(149,31,349,31,'normal response path')
        box(174,104,150,61,'Candidate bad health','Never becomes the active target',fill=colors.HexColor('#FFF2EC'),stroke=AMBER)
        arrow(248,104,248,66,'probe failure',dashed=True,color=AMBER)
        text(0,183,497,31,'Commit ROLLED_BACK, keep v1 target unchanged, then remove only the failed candidate.',9.4)
    elif kind=='recovery':
        labels=[('Persist intent','UUID + candidate name'),('Create candidate','Docker side effect'),('Process dies','No final SQL commit'),('Restart worker','Inspect same candidate')]
        for i,(a,b) in enumerate(labels):
            box(i*128,10,113,67,a,b,BLUE if i in (0,3) else PALE,BLUE if i in (0,3) else TEAL)
            if i<3: arrow(i*128+113,43,i*128+128,43)
        text(0,99,497,38,'Repeat the health gate and commit promotion. Deterministic identity makes replay converge; it does not make every operation execute once.',9.5)
    elif kind=='security':
        box(0,12,135,64,'Explicit bearer token','No ambient browser cookie')
        box(181,12,135,64,'Spring Security','Identity and operator role',BLUE,BLUE)
        box(362,12,135,64,'Service authorization','Owner or operator')
        arrow(135,44,181,44); arrow(316,44,362,44)
        box(181,126,135,64,'Runtime boundary','Fixed argv and local ports',BLUE,BLUE)
        box(362,126,135,64,'Docker authority','Host privileged control')
        arrow(429,76,248,126); arrow(316,158,362,158)
        text(0,206,497,27,'A restricted workload does not make Docker daemon access a restricted capability.',9.4)
    elif kind=='network':
        box(0,5,136,62,'Browser or client','127.0.0.1:8088')
        box(183,5,134,62,'Native Java server','Reads active_port',BLUE,BLUE)
        box(364,5,133,62,'Docker workload','host ephemeral port<br/>container port 8000')
        arrow(136,36,183,36); arrow(317,36,364,36)
        text(0,86,497,34,'With a bridged control plane container, 127.0.0.1 is that container itself. The native host path is the verified full Windows runtime.',9.3)
    elif kind=='ci':
        labels=[('Maven','17 integration tests'),('Build images','workload and control plane'),('Live acceptance','real HTTP and Docker'),('Upload evidence','reports and runtime JSON')]
        for i,(a,b) in enumerate(labels):
            box(i*128,8,113,66,a,b,BLUE if i==0 else PALE,BLUE if i==0 else TEAL)
            if i<3: arrow(i*128+113,41,i*128+128,41)
    elif kind=='future':
        text(0,0,497,22,'PROPOSED PRODUCTION EVOLUTION  /  NOT IMPLEMENTED',9.4,AMBER,True)
        box(0,42,130,62,'Identity and ingress','OIDC, TLS and authorization')
        box(184,42,133,62,'API replicas','Persist intent and outbox',BLUE,BLUE)
        box(366,42,131,62,'PostgreSQL','Lease and fencing state')
        arrow(130,73,184,73); arrow(317,73,366,73)
        box(184,163,133,62,'Worker fleet','Bounded concurrency and leases',BLUE,BLUE)
        box(366,163,131,62,'Runtime adapter','Persist ARM operation IDs')
        box(0,163,130,62,'App Service slots','Health gate, route and drain')
        arrow(431,104,250,163,'claim work'); arrow(317,194,366,194)
        c.setStrokeColor(BLUE); c.setLineWidth(1.1)
        c.line(431,height-225,431,height-241); c.line(431,height-241,65,height-241)
        arrow(65,241,65,225)
        text(100,225,300,14,'cloud operations and slot promotion',8.2)
        text(0,248,497,28,'The runtime API must reject stale fencing tokens or serialize effects; a SQL flag alone cannot fence an external cloud operation.',9.3)
    else: raise ValueError(kind)

def qa(p,question,answer):
    p.h(question); p.p(answer)

def build():
    HERE.mkdir(parents=True,exist_ok=True)
    c=canvas.Canvas(str(OUT),pagesize=(W,H),pageCompression=1)
    c.setTitle('Launchpad Project and Interview Handbook'); c.setAuthor('Vishal Kumar'); c.setSubject('Architecture, implementation, failure analysis and interview preparation')
    # Content pages are intentionally bounded so each topic has a readable page.
    build_pages(c)
    c.save(); print(OUT)

def build_pages(c):
    p=Page(c,1,'Launchpad project handbook','System design and interview preparation')
    p.p('A practical guide to the deployment control plane',ParagraphStyle('coverSub',parent=BODY,fontSize=16,leading=22,textColor=colors.black),15)
    p.p('Prepared for Vishal Kumar. Learn the system from the developer request to the Docker workload, understand why the failure paths work, and practise explaining the design under interview follow-up questions.')
    p.figure('cover',330,'A durable request becomes a real workload only after validation, runtime execution and a health gate. The database records which target the API should use.')
    p.table(['What has been demonstrated','Where'],[
      ['17 integration tests and nine real acceptance checks','Local verification on 14 October 2026'],
      ['Abrupt restart recovery and Terraform lifecycle','Local failure and infrastructure scenarios'],
      ['Tests, both image builds and live Docker acceptance','GitHub Actions run 38583306582']],[.64,.36])
    p.p('Source reviewed on 20 October 2026 at commit 7b11f3e. Historical verification is dated explicitly; this handbook does not claim a new test run today.',SMALL)
    p.finish()

    p=Page(c,2,'How to use this handbook','Reading map')
    p.p('First, learn the request flow and the three durable records. Next, work through failure and security boundaries. Finally, practise the question bank aloud. Use the PDF bookmarks or the links below to jump between topics.')
    sections=[('Project purpose and boundaries','3'),('Architecture and code responsibilities','4 to 5'),('Request sequence and deployment states','6 to 7'),('Database and API contract','8 to 9'),('Idempotency and concurrent requests','10 to 11'),('Health gate and rollback','12 to 13'),('Recovery and cleanup','14 to 15'),('Security and Docker networking','16 to 17'),('Observability and test evidence','18 to 19'),('Terraform and production evolution','20 to 21'),('Limitations and local operations','22 to 23'),('Screenshots and demonstration evidence','24 to 25'),('Question bank on product and APIs','26 to 27'),('Question bank on failures and security','28 to 29'),('Question bank on scale and cloud','30'),('Spoken explanations and demo script','31'),('Glossary and source references','32')]
    p.table(['Topic','Pages'],[[f'<link href="#p{re.match(r"[0-9]+",b).group()}" color="#087F83">{a}</link>',b] for a,b in sections],[.80,.20])
    p.h('A useful answer pattern')
    p.p('State the invariant, name the mechanism, walk through one failure, then state the boundary. Example: the old route must remain selected until the candidate is healthy; a SQL transaction commits the new route only after three consecutive probes; a bad candidate leaves the old target unchanged; request draining is still future work.')
    p.finish()

    p=Page(c,3,'The problem and the project scope','Product reasoning')
    p.h('The developer problem')
    p.p('A deployment is more than starting a container. A developer needs to request a release without knowing every runtime command. The platform must authorize the request, avoid duplicate work after retries, keep a useful history, and prevent an unhealthy candidate from taking over the active service route. Launchpad implements that narrow workflow end to end on a local machine.')
    p.h('What a control plane means here')
    p.p('The control plane decides and records what should run. Its API accepts deployment intent; its worker performs the slow runtime work. The workload container is the application being run. Launchpad also includes a small response proxy for the demonstration, so the control plane participates in that sample response path. It is not a separate production ingress layer.')
    p.h('Three terms to keep distinct')
    p.table(['Term','Meaning in this repository'],[
      ['Service','A named resource owned by one principal, with one active target.'],
      ['Deployment','A durable request to run an allowlisted release under dev or prod approval policy.'],
      ['Release','v1, v2 or bad-health, supplied as APP_VERSION to the same sample image.']],[.22,.78])
    p.h('The release fixture is deliberately small')
    p.p('The sample Python server returns a greeting for v1 and v2, while bad-health returns 503 on /health. These values exercise the lifecycle; they are not three independently built application images. The administrator-configured image tag launchpad-workload:local can be changed locally. An allowlist and --pull=never do not make a mutable tag an immutable artifact.')
    p.h('What makes the project platform engineering')
    p.p('It offers a repeatable developer path with guardrails, resource ownership, approval policy, runtime isolation and operational evidence. The differentiating work is the lifecycle and its failure boundaries. There is no Kubernetes cluster, deployed Azure control-plane adapter, LLM workflow or production availability measurement in the current project.')
    p.p('Explain it as a verified local deployment platform with a clear path to production hardening, rather than as a finished enterprise platform.',SMALL)
    p.finish()

    p=Page(c,4,'The system at a glance','Architecture')
    p.figure('overview',330,'The API persists intent before the worker performs Docker operations. A dashed line represents the demonstration response proxy. Runtime and SQL effects are not one transaction.')
    p.h('The synchronous boundary')
    p.p('The request thread authenticates, validates, locks and stores intent. It returns HTTP 202 with a deployment ID. The client can poll status and audit events instead of holding a connection through container startup and health checks.')
    p.h('The asynchronous boundary')
    p.p('A scheduled worker reads QUEUED and DEPLOYING rows. It claims or resumes an intent, ensures a deterministic candidate exists, probes it, then commits a result. Slow Docker and HTTP calls occur outside SQL transactions.')
    p.h('The durable boundary')
    p.p('File-backed H2 stores services, deployments and audit events; Flyway creates the schema. The current design assumes one process and one worker. The database is also the work queue, so no separate broker is required for this lab. Its role is durable coordination, not just CRUD storage.')
    p.finish()

    p=Page(c,5,'Where each responsibility lives','Code navigation')
    p.table(['Component','Responsibility','Start reading here'],[
      ['LaunchpadApplication','Bootstraps Spring and scheduling','main and @EnableScheduling'],
      ['SecurityConfig','Bearer identity and route role checks','security and the token filter'],
      ['ApiController','JSON validation and HTTP endpoints','Register and Deploy records'],
      ['ControlPlane','Ownership, quota, idempotency and policy','submit, approve and cancel'],
      ['Store','SQL queries and record mapping','lockedService, byKey and status'],
      ['DeploymentWorker','Claim, health gate, promotion and cleanup','execute and cleanupRetired'],
      ['WorkloadRuntime','Runtime abstraction','ensureStarted, healthy, remove, response'],
      ['DockerRuntime','Docker CLI and bounded HTTP requests','ensureStarted and command'],
      ['ApiErrors','Application error translation','ProblemDetail response'],
      ['Static dashboard','Token input, forms, polling and timeline','app.js refresh and api helpers']],[.27,.40,.33])
    p.h('Why JDBC and TransactionTemplate')
    p.p('The important behavior is explicit SQL locking and a small set of state changes. JdbcTemplate keeps those operations visible. TransactionTemplate groups them into a commit or rollback without keeping transactions open around Docker calls. Store is a Spring repository proxy; internal callers use Store.jdbc() rather than reading a field from the proxy.')
    p.h('Dependency inversion in practical terms')
    p.p('DeploymentWorker depends on WorkloadRuntime. Production wiring uses DockerRuntime; integration tests inject a deterministic fake implementation. A future Azure adapter would need more than a class name: its operation IDs, health semantics, timeout handling and compensation must be designed and verified.')
    p.p('Read this order when explaining code: API validation, ControlPlane.submit, Store.lockedService, DeploymentWorker.execute, then DockerRuntime.ensureStarted.',SMALL)
    p.finish()

    p=Page(c,6,'One deployment from request to response','Request sequence')
    p.figure('sequence',341,'The response acknowledges persisted intent. The worker can start soon after commit, so the returned object and a subsequent GET can show different valid states.')
    p.h('Walk the request through the implementation')
    p.p('The developer posts release v1 and environment dev with an Idempotency-Key. ApiController validates the JSON and header. ControlPlane authorizes the service, locks its row, checks prior key usage and rejects another in-flight intent. It creates the deployment UUID, candidate name and REQUESTED audit event in one transaction.')
    p.p('The worker later records DEPLOYING, starts or reuses the named candidate, and requires a healthy streak. In a second transaction it updates active_release, active_container and active_port together with SUCCEEDED and its event. It then retires old or failed containers through cleanup reconciliation.')
    p.h('What the client actually sees')
    p.p('The dashboard polls every three seconds. This is UI refresh, not the worker schedule. The worker uses a one-second fixed delay after a tick finishes. A long deployment can therefore delay later intents even when their API requests have already returned 202.')
    p.finish()

    p=Page(c,7,'The deployment state machine','Lifecycle invariants')
    p.figure('states',250,'Every transition is explicit. A production approval changes WAITING_APPROVAL to QUEUED; it does not skip the health gate.')
    p.table(['State','Meaning','Can an owner cancel'],[
      ['WAITING_APPROVAL','Persisted prod intent awaiting an operator','Yes'],
      ['QUEUED','Ready for a worker to claim','Yes'],
      ['DEPLOYING','Candidate execution or restart reconciliation','No'],
      ['SUCCEEDED','Health gate passed and target promoted','No'],
      ['ROLLED_BACK','Failure while a prior active target exists','No'],
      ['FAILED','Failure without a prior active target','No'],
      ['CANCELLED','Pending work cancelled before execution','Already terminal']],[.29,.54,.17])
    p.p('CLEANED, APPROVED and RECONCILED are audit event types, not deployment states. State does not encode every external fact: ROLLED_BACK means a prior target remained selected; it does not prove that target is still healthy at that instant. Missing containers after manual cleanup can leave a historical active target until another deployment changes it.')
    p.finish()

    p=Page(c,8,'The database is the coordination model','Data design')
    p.figure('erd',224,'One service has many deployment intents; one intent has many audit events. The key uniqueness rule is scoped to the authenticated requester, across all of that requester\'s services.')
    p.table(['Record','Why it exists'],[
      ['services','Authoritative ownership and active target. name is globally unique; there is no separate tenant identifier.'],
      ['deployments','Durable work queue and history, including request parameters, state and candidate identity.'],
      ['audit_events','Ordered per-deployment timeline with actor, event type, detail and timestamp.'],
      ['quota_lock','One fixed row serializes service registration while the five-service quota is checked.']],[.25,.75])
    p.h('Constraints and indexes that matter')
    p.p('A unique constraint on (requested_by, request_key) protects retry identity even when two transactions lock different service rows. Foreign keys preserve service and deployment relationships. A status and created_at index supports queue reads; a deployment_id and id index supports timeline reads. Event IDs determine timeline ordering.')
    p.h('A deliberate limitation')
    p.p('Busy checks and cleanup still read historical records into memory. There is no history retention policy, archive, cleanup task table or dedicated durable attempt count. Those omissions are acceptable for the lab, but matter before a long-running service handles large histories.')
    p.finish()

    p=Page(c,9,'The API contract and error model','HTTP design')
    p.p('All paths below are under /api. Supply an explicit bearer token. Service registration and deployment submission require application/json; unknown JSON properties are rejected.')
    p.table(['Method','Path','Result'],[
      ['GET','/me','Identity and operator flag'],
      ['GET / POST','/services','Owned catalog / register service with 201'],
      ['GET','/services/{name}','Service and active target'],
      ['GET / POST','/services/{name}/deployments','History / persist intent with 202'],
      ['GET','/deployments/{id}','Current durable state'],
      ['POST','/deployments/{id}/approve','Operator approval'],
      ['POST','/deployments/{id}/cancel','Owner or operator cancellation'],
      ['GET','/deployments/{id}/events','Ordered audit timeline'],
      ['GET','/services/{name}/response','JSON from the active workload']],[.16,.49,.35])
    p.h('Interpret failures precisely')
    p.table(['Status','Interpretation'],[
      ['400','Invalid body, unknown property, missing or malformed key.'],
      ['401 / 403','Missing or invalid identity / authenticated identity lacks required role.'],
      ['404','Resource is missing or outside a developer\'s ownership scope.'],
      ['409 / 422','Conflicting key or busy/wrong state / five-service quota exceeded.'],
      ['502 / 503','Previously selected workload unavailable / no active target exists.']],[.20,.80])
    p.p('ApiException becomes a Spring ProblemDetail. Security failures return a small application/problem+json response containing status and detail. The implementation is useful standardized error handling, but it does not populate a full custom problem taxonomy or correlation ID on every failure.',SMALL)
    p.finish()

    p=Page(c,10,'Idempotency protects request intent','Retries and deduplication')
    p.figure('idempotency',178,'The service lock handles requests for one resource. The actor and key constraint closes a different race: simultaneous reuse of one key across different resources.')
    p.h('A retry after an ambiguous response')
    p.p('Imagine the insert commits, but the client never receives the HTTP response. Retrying with the same key, service, release and environment returns the original deployment UUID and its current state. Reusing the key for a different intent returns 409. The response may now be SUCCEEDED rather than the original QUEUED state; replay identity is stable, response state is current.')
    p.code('''BEGIN
  SELECT service FOR UPDATE;
  find previous by authenticated actor and request key;
  if found: compare service, release and environment;
  otherwise: reject busy service and insert intent + event;
COMMIT''')
    p.h('What this does and does not guarantee')
    p.p('It deduplicates intent creation, not all side effects forever. Runtime operations can be retried after a crash, and metrics can reset or miss an increment. There is no key-expiry job; uniqueness remains as long as the deployment row remains. The dashboard retains a key for retries of the same intent while the tab remains open, but a reload loses that in-memory key.')
    p.p('Interview phrase: I made creation idempotent at the durable intent boundary, and made runtime execution replayable using the candidate identity.',SMALL)
    p.finish()

    p=Page(c,11,'Concurrency is controlled at two levels','Locking and transactions')
    p.figure('locking',142,'A row lock is held only through the decision and SQL changes. A request waiting on a lock does not get to decide using stale in-flight state.')
    p.h('Same service submissions')
    p.p('submit locks the services row before checking key replay and busy state. If request A inserts an intent, request B waits and then observes it. B either replays the same intent or rejects a new one as busy. Approval, cancellation and the worker claim use the same resource lock, which serializes their decisions against submission.')
    p.h('Service registration quota')
    p.p('Registration locks quota_lock row 1 before counting the owner\'s services and inserting. This prevents two requests from both consuming the final slot. The tradeoff is global contention: registrations by unrelated owners also wait on the same row. Per-owner lock rows or a transactional quota counter would improve that boundary.')
    p.h('Worker exclusion is narrower')
    p.p('tick and execute are synchronized methods in one Java process. The scheduled loop processes deployments serially. This is simple, but a slow job delays other services. synchronized is not a distributed lease, and embedded H2 file locking is not a design for active-active workers.')
    p.h('Why not hold a transaction through Docker')
    p.p('A slow image runtime or probe should not hold database locks for tens of seconds. Claim state in one short transaction, perform external work without SQL locks, then commit the result in another short transaction. A crash between those steps is handled through reconciliation, not by pretending Docker joined the SQL transaction.')
    p.finish()

    p=Page(c,12,'The health gate before promotion','Readiness policy')
    p.figure('health',130,'This sequence is illustrative, not a recorded benchmark. Each failure restarts the streak at zero.')
    p.table(['Setting','Current default','Purpose'],[
      ['Required streak','3 HTTP 200 responses','Avoid promoting on one transient success'],
      ['Maximum attempts','60','Bound repeated probe work'],
      ['Delay between probes','500 ms','Space out attempts'],
      ['Health deadline','30 seconds','Bound the post-start gate'],
      ['HTTP connect / read','2 seconds each','Bound individual network operations'],
      ['Docker CLI command','60 seconds','Bound each external process call']],[.37,.23,.40])
    p.h('Read the timing policy carefully')
    p.p('The deadline begins after ensureStarted returns the candidate\'s port. A probe that starts before the deadline may finish after it, and the last sleep can also extend wall-clock time. Several Docker CLI operations precede the gate, each with its own timeout. Therefore 30 seconds is not an end-to-end deployment SLA, and a healthy cold start can legitimately fail the gate on a slow host.')
    p.h('What a health endpoint proves')
    p.p('The sample server\'s /health proves its fixture is ready to return the demo response. It does not test a real database dependency, migration compatibility, customer traffic or performance under load. A production readiness contract must reflect the workload\'s dependencies without making every transient dependency problem trigger an unsafe rollout.')
    p.finish()

    p=Page(c,13,'Rollback preserves the selected target','Promotion semantics')
    p.figure('rollback',220,'The failed candidate never replaces the service target. Launchpad does not need to restart v1 to retain the route to it.')
    p.h('A failed upgrade')
    p.p('While bad-health is tested, services.active_container and active_port still point to v1. On failure, the worker sees that an active container field exists, records ROLLED_BACK and leaves the target unchanged. It later removes the failed candidate. A failed first deployment becomes FAILED because there is no prior target to preserve.')
    p.h('A successful upgrade')
    p.p('After the healthy streak, one SQL transaction updates all active target fields and records SUCCEEDED. Cleanup then retires the old container. A request that read the old port just before retirement can fail; the demo has no connection draining. This is why zero-downtime deployment is not an established project claim.')
    p.h('The boundary interviewers may test')
    p.p('The worker does not probe the old active target before declaring ROLLED_BACK. It preserves the previously promoted route, which may itself have become unhealthy. It also does not undo database schema changes, outbound messages or arbitrary application side effects. Backward-compatible releases and migration strategy are separate production design requirements.')
    p.p('A precise claim is health-gated promotion with preservation of the prior target on candidate failure. Avoid claiming complete application rollback or continuous self-healing.',SMALL)
    p.finish()

    p=Page(c,14,'Recovery across a process crash','Durable reconciliation')
    p.figure('recovery',146,'The restart test kills an exact child Java process while the durable intent is DEPLOYING, then opens the same database and checks the same real container ID.')
    p.table(['Crash window','What a restarted worker does'],[
      ['Before intent commit','No durable request exists; the client retries with its key.'],
      ['After intent commit','Find QUEUED work on a later scan.'],
      ['After claim before run','Resume DEPLOYING and create its named candidate.'],
      ['After Docker run','Inspect namespace, start or reuse that same name, then probe.'],
      ['After promotion commit','Keep the persisted active route and reconcile retirement.'],
      ['During removal','Retry terminal cleanup until removal is confirmed.']],[.34,.66])
    p.h('Why deterministic names matter')
    p.p('ControlPlane creates namespace + deployment UUID once and persists it as candidate_container. Replaying does not generate a new name. DockerRuntime inspects the object, checks its namespace label and reuses it. The RECONCILED event exposes the resumption rather than hiding it.')
    p.h('What was actually verified')
    p.p('The recovery script observed DEPLOYING, killed the child server, restarted with the same H2 file, asserted the same Docker container ID, checked RECONCILED and SUCCEEDED, and called the healthy workload. That is a demonstrated crash window. It is not exhaustive verification of every kill point or graceful shutdown path.')
    p.finish()

    p=Page(c,15,'Cleanup and external side effects','Operational correctness')
    p.h('History doubles as the cleanup ledger')
    p.p('cleanupRetired scans each service\'s deployment history. A terminal candidate is eligible if it is not the current active container and its events do not already include CLEANED. The runtime checks its namespace before removal. Only a confirmed removal creates the CLEANED event; an error is logged so the next scan can try again.')
    p.code('''for each service and historical deployment:
  if terminal and candidate is not the current active target:
    if no CLEANED event:
      inspect ownership and remove candidate
      append CLEANED only after success''')
    p.h('Absence is a valid cleanup outcome')
    p.p('A missing container is already removed. The isolated acceptance helper also handles a race where the killed worker already dispatched removal: it confirms eventual absence instead of treating every nonzero rm exit as a leak. A daemon failure must remain distinguishable from a missing object.')
    p.h('Reconciliation is not unlimited automatic retry')
    p.p('A live QUEUED or DEPLOYING row can be resumed after interruption. An ordinary Docker or health exception normally produces FAILED or ROLLED_BACK; that deployment is not automatically retried as a new deployment. The client submits a new intent with a new key after addressing the cause. Cleanup, in contrast, keeps retrying while it lacks a CLEANED event.')
    p.h('Edges still worth hardening')
    p.p('A timed-out CLI process does not prove the daemon never created a container. Graceful interruption inside DockerRuntime is wrapped differently from interruption during the worker\'s sleep. Ancillary metric failures also sit inside the worker\'s broad success/failure try block. Production hardening should test these boundaries and separate committed promotion success from later instrumentation failures.')
    p.p('At scale, use indexed pending cleanup tasks and backoff rather than scanning all history and event lists every tick. Keep that change separate from the current demonstrated implementation.',SMALL)
    p.finish()

    p=Page(c,16,'Identity roles and ownership','Security design')
    p.figure('security',238,'Authentication identifies the caller; route role checks and resource ownership authorize actions. The Docker engine remains a separate, powerful trust boundary.')
    p.table(['Action','Developer','Operator'],[
      ['List and inspect services','Own resources','All resources'],
      ['Register a service','Owned by caller','Owned by caller'],
      ['Request deployments','Owned service','Any service'],
      ['Approve production intent','Denied','Allowed'],
      ['Cancel pending work','Owned service','Any service'],
      ['Scrape Prometheus','Denied','Allowed']],[.46,.27,.27])
    p.p('Three static tokens resolve to vishal, other-team and platform-ops. The filter compares explicitly supplied bearer bytes and stores a Spring Security Authentication for the request. Tokens must be distinct and at least 24 characters. This is a lab identity mechanism, with no expiry, rotation endpoint, JWT validation or identity-provider discovery.')
    p.p('Ownership is fixed at registration. Cross-owner developer reads return 404 to avoid disclosing resource existence. Operators have broad access, and an operator can approve an intent they requested; this is role separation, not an enforced two-person approval rule. A prod field on an intent does not prevent a later dev-policy request from replacing that same service slot.')
    p.finish()

    build_remaining_pages(c)

def build_remaining_pages(c):
    p=Page(c,17,'Docker isolation and host networking','Runtime design')
    p.figure('network',132,'The API response endpoint proxies to a port stored in SQL. It does not accept an arbitrary user-provided URL.')
    p.table(['Runtime choice','What it achieves','What it does not achieve'],[
      ['UID 10001 and read-only root','Reduce default write and privilege scope','Do not remove daemon authority'],
      ['Drop all capabilities','Remove optional kernel capabilities','Do not eliminate kernel vulnerabilities'],
      ['No new privileges','Prevent privilege gains through exec','Is not a complete sandbox'],
      ['64 MiB and 0.25 CPU','Constrain each API-managed workload','Do not cap total platform demand'],
      ['64 PIDs','Bound process proliferation','Do not provide tenant-level fairness'],
      ['Loopback ephemeral ports','Avoid normal external host ingress','Local host processes can connect'],
      ['Fixed image and argv','Prevent client-selected commands or mounts','Local image tags are still mutable']],[.29,.35,.36])
    p.h('Why native Java is the Windows golden path')
    p.p('The worker publishes workload ports on the Docker host and connects to host loopback. A bridged control-plane container sees its own loopback instead. The documented Linux host-network example also needs Docker socket access and suitable group permissions. The packaged image smoke check disabled the worker; it proved health, identity, the API contract and non-root packaging, not the full containerized adapter path.')
    p.p('The local Terraform module uses an immutable image ID and cpu_shares = 256. CPU shares are a relative scheduling weight; they are not the same setting as the API runtime\'s hard 0.25 CPU limit.',SMALL)
    p.finish()

    p=Page(c,18,'Observability and operational diagnosis','Signals and their limits')
    p.table(['Signal','Current implementation','How to use it'],[
      ['Control-plane health','Public /actuator/health with details hidden','Check that the service and configured health contributors respond'],
      ['Workload probes','Candidate /health during deployment','Explain the gate decision, not continuous availability'],
      ['Outcome counter','launchpad.deployments with result tag','Count in-process success and failed outcomes'],
      ['Duration timer','launchpad.deployment.duration','Observe the timed worker section around runtime work'],
      ['Queue gauge','launchpad.queue.depth','Count QUEUED plus DEPLOYING rows'],
      ['Audit events','Persisted UUID, actor, type, detail, time','Reconstruct decisions after restart'],
      ['Application logs','Deployment, service, outcome and bounded reason','Locate runtime errors and pending cleanup']],[.24,.41,.35])
    p.h('Two health questions with different answers')
    p.p('An UP control-plane endpoint does not mean the Docker daemon or every active workload is healthy. The control plane can still accept requests and read its database while an active workload is unavailable. A response API call to a previously selected but unreachable workload returns 502. There is no continuous watchdog that automatically restores or replaces that workload.')
    p.h('The numbers are not durable accounting')
    p.p('Counters and timers live in the process and reset after restart. A crash after the SQL promotion but before a counter increment can leave a successful deployment without that metric update. The timer is not the client\'s queue-to-completion time; it starts after claim. Use durable rows and timestamps for historical accounting, and instrument queue wait separately before defining an SLO.')
    p.h('Useful next signals')
    p.p('Add oldest pending age, approval wait, cleanup backlog, worker heartbeat and per-stage latency. Use bounded labels such as outcome and runtime type, rather than UUIDs or unbounded service names on every metric. Distributed tracing, alert delivery, dashboards and a measured error budget are future work, not current project features.')
    p.finish()

    p=Page(c,19,'What the tests actually establish','Evidence and CI')
    p.figure('ci',85,'Remote GitHub Actions passed this pipeline for source commit cd73304 on 14 October 2026. The exact run is linked in the source references.')
    p.table(['Layer','Coverage','Boundary'],[
      ['17 integration tests','Spring API, real in-memory H2, transactions and a fake runtime','Does not prove Docker networking'],
      ['Nine live acceptance checks','Real HTTP, Docker containers, failures, approvals and metrics','Functional scenarios, not load testing'],
      ['Abrupt restart scenario','Same file DB and real container ID reused after kill','One important crash window'],
      ['Container package smoke','Non-root package, health, identity and API contract','Worker was disabled'],
      ['Terraform local lifecycle','Create, health check, no-change plan and destroy','Independent golden workload'],
      ['Azure reference validation','Provider and configuration schema accepted','No cloud plan or apply']],[.26,.43,.31])
    p.h('Know the integration test groups')
    p.p('Authentication and ownership tests cover anonymous rejection, cross-team reads and writes, timelines and operator-only metrics. Contract tests reject malformed and unknown input. Lifecycle tests cover idempotency, concurrent replay, busy service conflicts, approval, cancellation, quota, promotion, first failure, rollback, reconciliation, Docker failure, flapping health and retryable cleanup.')
    p.h('How to present the evidence')
    p.p('Say exactly what ran and where. The local record and GitHub result are dated 14 October 2026. This handbook rechecked the source on 20 October; writing it did not rerun the whole platform. The remote workflow does not execute the separate abrupt-restart script or Terraform lifecycle. Test counts are verified outcomes, not business impact or performance metrics.')
    p.p('Examples of work still to add: database failure during final commit, stale-worker races, graceful shutdown at every external call, concurrent key reuse across services, prolonged daemon outage, draining and history retention. A good test suite demonstrates defined behavior; it does not prove every possible failure safe.',SMALL)
    p.finish()

    p=Page(c,20,'Terraform and the Azure boundary','Infrastructure automation')
    p.table(['Aspect','Local Docker module','Azure reference'],[
      ['Provisioned resource','One independent golden workload','Resource group, B1 plan and Linux Web App'],
      ['Artifact reference','Validated sha256 image ID','Published image digest required'],
      ['Exposure','127.0.0.1 port 8099 by default','Public HTTPS workload endpoint'],
      ['Security settings','Non-root, read-only, capability restrictions','TLS minimum, HTTPS-only, system identity'],
      ['Health behavior','HTTP checked during verification','App Service health path configured'],
      ['Evidence','Apply, HTTP 200, no drift, destroy','Init and provider validate only'],
      ['Control-plane integration','Not called by the worker','No Azure runtime adapter implemented']],[.26,.36,.38])
    p.h('Why two owners must not manage one container')
    p.p('The API runtime and Terraform demonstrate the same workload contract independently. They use different namespace labels and names. If Terraform and the worker both owned one container, one could replace or remove it while the other believed it was active. Pick one authoritative owner for each resource and make handoffs explicit.')
    p.h('What the local no-drift check means')
    p.p('After apply, the HTTP endpoint returned a healthy greeting. A detailed plan returned exit code 0 with no changes, then destroy removed the resource. Docker defaulted memory_swap to 128 MiB, so that value was set explicitly to avoid perpetual drift. This tests convergence for this local fixture, not a cloud deployment strategy.')
    p.h('What an Azure implementation would require')
    p.p('App Service does not provide the host Docker daemon expected by this adapter. A real Azure runtime would use managed identity and ARM APIs, store long-running operation IDs, poll operations, check the target slot, promote routing and reconcile failures. Private ACR also needs its own identity-based pull configuration. The B1 reference can incur cost; none was provisioned for this project.')
    p.finish()

    p=Page(c,21,'A credible path to production','Proposed system design')
    p.figure('future',284,'This is a design proposal, not a diagram of deployed functionality. Start with the current invariants, then add distributed coordination and a cloud-specific runtime contract.')
    p.h('Separate serving from orchestration')
    p.p('Use a dedicated ingress and workload serving path so control-plane unavailability does not stop normal application traffic. Add connection draining around promotions. Model release artifacts by immutable digest and require compatibility checks for migrations and dependencies.')
    p.h('Make work ownership explicit')
    p.p('Move durable state to PostgreSQL with migrations and backup policy. Claim eligible jobs transactionally, store worker identity, lease expiry, attempt count and a monotonically increasing fencing token. A heartbeat renews the lease. Every status update must prove ownership. External effects need equivalent stale-worker rejection or serialized runtime operations.')
    p.h('Grow the runtime contract rather than rename it')
    p.p('An asynchronous cloud API needs submit, inspect, health, promote and remove semantics with persisted remote operation IDs. A broker can wake workers efficiently, but the database remains authoritative. If using a broker, an outbox avoids a gap between committing intent and publishing its notification. Test API crash, expired lease and partially completed cloud operations before scaling workers.')
    p.finish()

    p=Page(c,22,'The limitations worth explaining well','Critical design review')
    p.h('One worker limits fairness and throughput')
    p.p('A long health gate blocks later intents for other services because the scheduled loop is serial. Fixed delay means the next scan begins after the current tick completes and another second elapses. Do not describe this as a job starting within one second. First add queue-age metrics, then bounded per-service concurrency and durable leases.')
    p.h('A history scan is not a scalable queue strategy')
    p.p('Submission scans service history to find a busy state. Cleanup scans services, deployments and event lists. Queue order uses created_at without a tie-breaking ID. Add targeted existence queries, stable ordering, retention, indexed pending cleanup records and an explicit one-active-intent invariant before expecting high cardinality.')
    p.h('Approval policy needs a protected resource model')
    p.p('An intent says dev or prod, but the service has one active slot. A later dev intent can replace the same service without production approval. Operators can also approve their own requests. Protected environment resources and optional requester-versus-approver constraints would be needed for stronger governance.')
    p.h('The runtime trust model is local')
    p.p('Labels prevent accidental cross-namespace cleanup; they do not defend against a host administrator who can spoof labels or replace images. A matching namespace is not image attestation. The configured tag is mutable. Use digest pinning, artifact verification and a constrained remote runtime rather than broad host daemon access for untrusted tenants.')
    p.h('Failure domains are not fully separated')
    p.p('H2, the worker and the response proxy share one process/host boundary. The code does not continuously revalidate active targets, drain old requests or restore lost database files. Promotion instrumentation should also be isolated from deployment failure handling. Be ready to name these limitations and explain the next test that would reduce each uncertainty.')
    p.finish()

    p=Page(c,23,'Run and diagnose the local project','Practical operations')
    p.p('From the launchpad project directory, start Docker Desktop in Linux-container mode. The native Java path is the demonstrated full Windows deployment route. A first build requires dependency and base-image network access.')
    p.code('''# Builds workload, runs tests, packages and starts Java
./scripts/start.ps1

# Reuse the existing jar and workload image
./scripts/start.ps1 -SkipBuild

# Independent real scenarios on separate ports
python scripts/acceptance.py
python scripts/recovery.py

# Stop the server before rebuilding or manual cleanup
./scripts/cleanup.ps1''')
    p.p('Default API port is 8088; isolated acceptance uses 8091 and recovery uses 8090. Docker assigns ephemeral workload host ports. The dashboard accepts the documented local demo token. Configure distinct random environment tokens for any non-demo use; these static sample credentials are public fixtures, not real secrets.')
    p.table(['Symptom','Check and explanation'],[
      ['Java loopback exception','Use start.ps1. Its non-existent NIO fallback path addresses this Windows launch environment.'],
      ['Maven cannot rename jar','Stop the running native process before repackaging on Windows.'],
      ['Candidate fails unexpectedly','Inspect Docker logs, gate debug logs, CPU and cold-start timing. Retained route is the intended failure behavior.'],
      ['Five-service quota','Reuse a service or run the isolated acceptance script with a fresh database/namespace.'],
      ['Active response is 502','Check whether the recorded container is running; the platform does not automatically heal an active target.'],
      ['Ports work natively but not in container','Check loopback namespaces and documented host-network requirements.']],[.32,.68])
    p.p('Manual cleanup preserves SQL history while removing labelled containers. That can leave active fields pointing at removed objects. A new deployment or an intentionally fresh database/namespace restores a coherent demonstration; do not call deletion of runtime state a rollback.',SMALL)
    p.finish()

    p=Page(c,24,'See a healthy release survive failure','Demonstration evidence')
    p.p('These are genuine screenshots from the local checkout-api demonstration on 14 October 2026. The API, history and response panels describe actual Docker workload behavior.')
    p.image(Path('evidence/screenshots/01-healthy-deployment.png'),'Healthy baseline  v1 is selected and its deployment is SUCCEEDED. The response is visible in the next scenario.')
    p.image(Path('evidence/screenshots/02-failed-upgrade-retains-v1.png'),'Failure injection  bad-health became ROLLED BACK while the active response remained healthy v1.')
    p.p('When presenting, point first to the selected service, then the release state, then the response. A screenshot illustrates the result; the acceptance script and audit records provide stronger reproducible evidence.',SMALL)
    p.finish()

    p=Page(c,25,'See approval and attributable promotion','Demonstration evidence')
    p.image(Path('evidence/screenshots/03-production-approval-gate.png'),'Approval gate  the operator can approve a WAITING APPROVAL intent while v1 remains the selected target.')
    p.image(Path('evidence/screenshots/04-approved-promotion-audit.png'),'Attribution  APPROVED records platform-ops, followed by DEPLOYING and SUCCEEDED. The workload response is now v2.')
    p.p('The developer approval rejection is established by API tests, not by hiding a button. The screenshots also show the precise policy scope: one local active slot per service. Explain that scope before discussing a protected production environment design.',SMALL)
    p.finish()

    p=Page(c,26,'Interview questions on product and design','Question bank 1 of 5')
    qa(p,'1 What did you build','I built a Java and Spring Boot control plane for developer-requested local deployments. It persists intent, applies ownership and approval rules, starts real Docker candidates and promotes only after a health gate. I verified retries, failed upgrades, recovery and infrastructure convergence rather than inventing impact metrics.')
    qa(p,'2 Why is this more than a CRUD application','The SQL records coordinate external side effects and enforce lifecycle invariants. The interesting behavior is what happens after an ambiguous retry, conflicting request, failed health gate or process crash. The tables support those decisions; they are not the project\'s end goal.')
    qa(p,'3 Why return 202','A committed request can wait for approval, queueing or runtime work. Returning 202 exposes that asynchronous contract. The deployment ID gives the client a durable status resource instead of coupling it to a long-lived HTTP request that may disconnect during startup.')
    qa(p,'4 Why one worker and H2','They make a reproducible local system feasible without a broker or managed database. I kept transactions explicit and tested important failure paths. I would not scale replicas by simply replacing the JDBC URL; distributed ownership, leases and external-effect fencing are separate design work.')
    qa(p,'5 Is this Kubernetes or a replacement for it','No. The current runtime uses Docker on one local host and a deliberately fixed sample image. The project demonstrates lifecycle coordination and a developer path. A Kubernetes adapter would still need deployment ownership, readiness, rollout status and reconciliation semantics.')
    qa(p,'6 What is the control plane and data plane distinction','The control plane accepts and coordinates desired changes. The workload containers serve the application. Launchpad\'s demo response endpoint proxies through the control plane, so those paths are not fully separated here. A production ingress should allow existing workloads to serve independently of orchestration availability.')
    qa(p,'7 Does production mean a deployed production environment','No. prod selects operator approval for an intent on the same local service slot used by dev. There is no separate environment resource or cloud boundary. That makes the approval behavior demonstrable, but stronger production governance requires protected environment identities and policy.')
    qa(p,'8 What is your strongest evidence','The recorded evidence includes 17 integration tests, nine real acceptance checks, same-container recovery after an abrupt process kill, and a local Terraform apply/no-drift/destroy cycle. GitHub CI separately passed tests, both image builds and live Docker acceptance for the linked source commit.')
    p.finish()

    p=Page(c,27,'Interview questions on APIs and SQL','Question bank 2 of 5')
    qa(p,'9 What if the client retries after a timeout','The key may already identify a committed deployment. The API looks up authenticated requester plus key and compares service, release and environment. A matching retry returns that deployment\'s UUID and current state; a mismatching payload returns 409. The retry must preserve its key.')
    qa(p,'10 What if the same key is used across services','Its scope is per requester across all services, not per service. A database unique constraint covers that pair. Two transactions can lock different service rows, so the uniqueness check and duplicate-key recovery remain important even though same-service requests are serialized.')
    qa(p,'11 Why lock the service row','The busy-state check and insert must behave as one decision for that service. Otherwise two requests can both see no active intent and insert competing deployments. SELECT FOR UPDATE serializes the check with other submissions, approval, cancellation and worker claim transactions.')
    qa(p,'12 Why not use synchronized everywhere','A Java monitor coordinates threads in one object instance. It does not protect another JVM or make a database decision atomic. Launchpad uses it for its single worker and SQL row locks for resource decisions. A worker fleet would need durable ownership and fencing.')
    qa(p,'13 Can the service quota race','The implementation locks one quota row before count-and-insert, preventing two registrations from both using the last slot. It serializes all registrations, including different principals. A per-owner counter or per-owner lock would reduce that contention while preserving the quota invariant.')
    qa(p,'14 Why not hold the transaction during health checks','That would hold locks while external operations wait and fail. Instead, the worker records a claim, performs runtime work outside SQL transactions, and commits the result later. The intervening crash windows are handled through deterministic identity and reconciliation, not distributed SQL rollback.')
    qa(p,'15 Is the API fully idempotent','Intent creation is idempotent for matching key and payload. Repeated cancellation of CANCELLED work also returns that record. Approval only replays cleanly while already QUEUED; after later states it can conflict. These are endpoint-specific behaviors, not a universal exactly-once API guarantee.')
    qa(p,'16 Why return 404 for another owner','It avoids confirming that the resource exists while denying access. The same check covers service reads, writes and event timelines. Operators intentionally have wider access. This is principal ownership isolation, not a complete organization and tenant membership model.')
    p.finish()

    p=Page(c,28,'Interview questions on failures and recovery','Question bank 3 of 5')
    qa(p,'17 What happens if the worker dies after Docker run','The DEPLOYING intent already stores a candidate name derived from its UUID. After restart the worker inspects that name, validates its namespace and reuses the candidate, then repeats health checks. The abrupt-kill scenario verified the same real Docker container ID after recovery.')
    qa(p,'18 Is this exactly once execution','No. A worker can repeat inspection, start and health checks. The design makes creation identity stable and recovery converge toward one durable result. A process crash can also leave metrics out of sync with history. Exactly-once external execution is not the project\'s claim.')
    qa(p,'19 Why three consecutive probes','One success can be transient. A consecutive streak resets after any failed probe and prevents promotion on an isolated healthy response. Three is a small demo policy, not a statistically established reliability threshold. A real service needs a readiness contract and a justified observation window.')
    qa(p,'20 What if the previous release is also unhealthy','The worker preserves the stored prior target and calls the outcome ROLLED_BACK if that field exists. It does not recheck that target during failure handling. I would describe this as retaining the last promoted route and add explicit active-target monitoring before claiming healthy recovery.')
    qa(p,'21 Why do you not claim zero downtime','A response request can read the old port immediately before cleanup removes that container. There is no drain interval or connection-aware ingress. Health-gated target changes reduce one rollout risk, but zero downtime would need serving-path design and appropriate traffic tests.')
    qa(p,'22 What if Docker times out but later creates a container','Killing the CLI does not undo work already accepted by the daemon. Persisted candidate identity and cleanup reconciliation help locate it. A production runtime should distinguish an unknown operation result from a confirmed failure, persist remote operation identifiers and test delayed completion explicitly.')
    qa(p,'23 What happens if cleanup fails','The deployment outcome remains durable, but no CLEANED event is appended. A later scan can try removal again. This decouples success or rollback from retirement. Backoff, an indexed cleanup queue and bounded history scans would be needed to make that mechanism efficient at scale.')
    qa(p,'24 What if an active workload dies later','The current system does not heal it automatically. The active response endpoint returns 502 when the target cannot provide a successful response. Candidate health gating and continuous active-workload reconciliation are different responsibilities. Monitoring, replacement policy and escalation would be a separate enhancement.')
    p.finish()

    p=Page(c,29,'Interview questions on security and runtime','Question bank 4 of 5')
    qa(p,'25 How are users authenticated','An explicit bearer token is compared against three configured demo tokens and resolves to a principal and role for the request. The tokens are distinct, at least 24 characters and have no expiry workflow. I would use OIDC-backed short-lived credentials and proper rotation in a deployed platform.')
    qa(p,'26 Why is CSRF disabled','The app expects credentials supplied explicitly in an Authorization header, without cookies, sessions or Basic authentication. The relevant property is absence of automatically attached browser credentials, not merely being stateless. If the authentication model changes, the CSRF decision must be revisited.')
    qa(p,'27 Does hiding Approve secure the operation','No. The server requires ROLE_OPERATOR for the approval route. The dashboard reflects the role for usability, while integration and acceptance checks verify a developer receives 403. Client-side visibility is not an authorization boundary.')
    qa(p,'28 How is command injection prevented','The client cannot supply arbitrary image names, shell commands, mounts or environment variables. Releases are validated, SQL uses parameters and Docker is invoked with a fixed ProcessBuilder argument list rather than a shell. Administrator-controlled image configuration still belongs to the trusted runtime boundary.')
    qa(p,'29 Is the image immutable','The API fixture uses a local tag and APP_VERSION, so no. --pull=never prevents a deployment-time pull but does not freeze the tag. The independent Terraform module accepts a sha256 image ID. A production artifact catalog should resolve approved releases to verified immutable digests.')
    qa(p,'30 Does non root make Docker access safe','It constrains the workload process, but daemon access can still provide broad authority over the host runtime. Resource limits, dropped capabilities and read-only root reduce specific risks; they do not make this a safe general platform for mutually untrusted tenants.')
    qa(p,'31 Are labels an access control system','They are an ownership guard against accidental reuse or deletion across namespaces. A host administrator can spoof them. The current reuse check matches the namespace; it is not cryptographic artifact attestation. Stronger isolation must come from the runtime and identity boundary.')
    qa(p,'32 Can you enforce two person production approval','The current operator role controls approval, but operators can request and approve their own intents. To require two people, persist requester and approver identities, reject equality and protect the destination environment independently of the request\'s dev or prod field.')
    p.finish()

    p=Page(c,30,'Interview questions on scale and cloud','Question bank 5 of 5')
    qa(p,'33 How would you add more workers','Use a shared transactional database, bounded claims, lease owner and expiry, attempt records and fencing tokens. Lock or claim by service to preserve promotion order. The external runtime must reject stale operations or serialize them. Adding threads alone does not create safe distributed coordination.')
    qa(p,'34 Would you add Kafka','Only if notification, fan-out or throughput requirements justify it. A database queue is sufficient for the current local scope. With a broker, use an outbox to avoid committing intent without publishing notification; consumers still need deduplication, durable ownership and runtime reconciliation.')
    qa(p,'35 What would you index or paginate first','Use a targeted active-intent existence query, a stable queue order and an indexed pending-cleanup table. Paginate service deployment history and audit events, then define retention. Current scans and N-plus-one event lookups are more immediate scaling issues than the choice of UI framework.')
    qa(p,'36 How would Azure fit','Implement a real runtime adapter using managed identity and ARM operations, persist operation IDs, poll status, probe a candidate slot and promote routing. Reconcile partial completion and manage private image pulls. The current Azure Terraform file is only a validated workload reference, not that adapter.')
    qa(p,'37 What would your first SLO measure','Define user-facing acceptance and deployment completion separately. Instrument queue wait, approval wait, runtime stage duration and failure reasons. Decide which waits the platform owns before calculating an SLI. The current timer does not measure full request-to-ready latency, and no target is measured or claimed.')
    qa(p,'38 What is the backup and disaster recovery plan','The current H2 file is local state without an implemented backup or tested host-loss recovery policy. A production design would define RPO and RTO, back up the shared database, test restores, and reconcile retained runtime objects against restored intent and route records.')
    qa(p,'39 What would you improve first','Separate telemetry failure handling from committed promotion, test ambiguous runtime outcomes and graceful shutdown, then improve queue and cleanup queries. Next add protected environments, immutable artifacts and identity integration. Multi-worker throughput should follow correctness tests and observability, not precede them.')
    qa(p,'40 Why did you leave AI out','The project\'s core value is reliable lifecycle coordination. An LLM is not needed to decide whether an HTTP health gate passed. A later assistant could summarize audit evidence or suggest diagnostics, while deterministic policy and authorized actions remain outside the model\'s discretion.')
    p.finish()

    p=Page(c,31,'Explain the project aloud','Narration and rehearsal')
    p.h('A thirty second introduction')
    p.p('I built Launchpad, a Spring Boot control plane for self-service local deployments. It stores deployment intent, enforces ownership and production approval, and runs real Docker candidates. A release becomes active only after three consecutive health checks. A failed candidate preserves the previous route. I verified concurrent retries, failure paths and recovery after killing the worker, and published reproducible evidence with passing GitHub CI.')
    p.h('A deeper explanation in about two minutes')
    p.p('The main design decision is to separate accepting a request from executing it. The API returns 202 only after a transaction stores the intent and audit event. It locks the service row so competing requests cannot both create active work. A requester-scoped idempotency key makes an ambiguous client retry return the same intent.')
    p.p('The scheduled worker claims that intent, performs Docker calls outside SQL transactions and probes the candidate. It persists the candidate name before execution, so a restart can inspect and reuse the same container. Promotion updates the active target and terminal status together. Cleanup is reconciled afterwards, allowing removal failures to retry without changing the deployment result.')
    p.p('The implementation intentionally uses one worker and file-backed H2 for reproducibility. Static bearer principals and a fixed sample image make the security and approval behavior testable. For a deployed platform I would add OIDC, immutable artifacts, a separate ingress, protected environments and a shared database with leases and fencing. The Azure reference is validated infrastructure code; I have not deployed an Azure adapter.')
    p.h('A five minute live demo')
    p.table(['Time','Show','Explain'],[
      ['0 to 1 min','Register service and deploy v1','Persisted intent, status and real response'],
      ['1 to 2 min','Deploy bad-health','Old target stays selected during the gate'],
      ['2 to 3 min','Inspect ROLLED_BACK and CLEANED','Failure result and cleanup are separate'],
      ['3 to 4 min','Request prod v2 and approve as operator','Server authorization and attributable approval'],
      ['4 to 5 min','Show recovery evidence and architecture','Crash window, same container and next tradeoff']],[.18,.40,.42])
    p.p('When challenged, use a concrete request or crash window instead of listing technologies. If a proposed feature is not implemented, say how you would add it and what you would test before claiming it.',SMALL)
    p.finish()

    p=Page(c,32,'Glossary and source references','Further reading')
    p.table(['Term','Plain meaning in this project'],[
      ['Intent','A persisted request describing the change to attempt.'],
      ['Invariant','A property that must remain true through concurrency or failure.'],
      ['Reconciliation','Compare durable state with runtime objects and repeat safe work.'],
      ['Idempotency','A matching retry refers to the same durable request.'],
      ['Atomic promotion','Update selected target and terminal state in one SQL commit.'],
      ['Lease and fencing','Proposed time-bound ownership plus rejection of stale workers.'],
      ['Outbox','Proposed durable notification record committed with the intent.'],
      ['Readiness and liveness','Able to serve the required workload / process still functioning.'],
      ['RPO and RTO','Acceptable data-loss window / target restoration time.']],[.29,.71])
    p.h('Primary project sources')
    base='https://github.com/alphaCoderVishal/launchpad'
    p.p(f'<link href="{base}" color="#087F83">Repository and runnable setup</link>  |  Source snapshot 7b11f3eb1a35dd23a7f833336fd84967cdffd949',SMALL)
    for label,path in [('API and validation','src/main/java/dev/launchpad/ApiController.java'),('Transactions and policy','src/main/java/dev/launchpad/ControlPlane.java'),('Worker and runtime','src/main/java/dev/launchpad/DeploymentWorker.java'),('Runtime side effects','src/main/java/dev/launchpad/DockerRuntime.java'),('Schema and indexes','src/main/resources/db/migration/V1__control_plane.sql')]:
        p.p(f'<link href="{base}/blob/7b11f3eb1a35dd23a7f833336fd84967cdffd949/{path}" color="#087F83">{label}</link>',SMALL,4)
    p.p(f'<link href="{base}/actions/runs/38583306582" color="#087F83">Passing GitHub CI run 38583306582</link>  |  Tested application source cd73304. See docs/verification.md and evidence/summary.json for local checks.',SMALL)
    p.h('Official background references')
    p.p('<link href="https://docs.spring.io/spring-security/reference/servlet/exploits/csrf.html" color="#087F83">Spring Security on CSRF</link> explains the role of automatically supplied browser credentials. <link href="https://docs.docker.com/engine/security/" color="#087F83">Docker Engine security</link> explains the daemon trust boundary. <link href="https://www.postgresql.org/docs/current/sql-select.html" color="#087F83">PostgreSQL SELECT locking clauses</link> provide background for the proposed shared work-claim design. These are reference concepts, not evidence that the proposed production changes are implemented.',SMALL)
    p.p('Technical descriptions were checked against the local source on 20 October 2026. Screenshots and execution evidence are from 14 October 2026. No new performance, production availability or Azure deployment claim is made.',SMALL)
    p.finish()

if __name__=='__main__': build()
