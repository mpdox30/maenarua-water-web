# สร้าง ui_lab_standalone.html (ไฟล์เดียว) จาก index.html + ui.css + data.js + ui.js
import os
d=os.path.dirname(os.path.abspath(__file__)); r=lambda n:open(os.path.join(d,n),encoding='utf8').read()
h=r('index.html').replace('<link rel="stylesheet" href="ui.css">','<style>\n'+r('ui.css')+'\n</style>')
h=h.replace('<script src="data.js"></script>','<script>\n'+r('data.js')+'\n</script>').replace('<script src="ui.js"></script>','<script>\n'+r('ui.js')+'\n</script>')
open(os.path.join(d,'ui_lab_standalone.html'),'w',encoding='utf8').write(h); print('ok',len(h))
