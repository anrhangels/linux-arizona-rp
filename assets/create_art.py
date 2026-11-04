#!/usr/bin/env python3
"""Original vector artwork for the Linux RP series. Standard pycairo only."""
from pathlib import Path
import cairo,math,random
P=Path(__file__).parent
BG='#11101B';INK='#F5EFEB';MUTED='#AEA5B9';ORANGE='#FFB076';LILAC='#B7A5F5';TEAL='#8FD0C4'
def col(c,h):c.set_source_rgb(*(int(h[i:i+2],16)/255 for i in (1,3,5)))
def rect(c,x,y,w,h,co):col(c,co);c.rectangle(x,y,w,h);c.fill()
def circle(c,x,y,r,co):col(c,co);c.arc(x,y,r,0,math.tau);c.fill()
def line(c,pts,co,w=1):
 col(c,co);c.set_line_width(w);c.move_to(*pts[0]);[c.line_to(*p) for p in pts[1:]];c.stroke()
def poly(c,pts,co):
 col(c,co);c.move_to(*pts[0]);[c.line_to(*p) for p in pts[1:]];c.close_path();c.fill()
def text(c,s,x,y,size,co=INK,font='Nimbus Sans',bold=False):
 c.select_font_face(font,0,cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL);c.set_font_size(size);col(c,co);c.move_to(x,y);c.show_text(s)
def pixelpalm(c,x,y,size=1):
 c.save();c.translate(x,y);c.scale(size,size)
 for i in range(14):rect(c,i//3*3,-i*8,8,10,'#141421')
 for side in [-1,1]:
  for k in range(6):rect(c,12+side*k*11,-116+(k*k)//2,15,6,'#141421')
  for k in range(5):rect(c,12+side*k*8,-112+k*8,12,6,'#141421')
 c.restore()
def scene(c):
 # Pixel sunset: hand-built silhouettes, not a game screenshot.
 rect(c,700,75,660,506,'#262139');circle(c,1040,264,121,'#F2A069')
 for y in range(212,393,15):rect(c,876,y,340,6,'#32243B')
 random.seed(71)
 for _ in range(75):rect(c,random.randrange(715,1340),random.randrange(88,220),2,2,'#6C587C')
 poly(c,[(700,367),(776,304),(814,332),(871,271),(943,339),(1017,307),(1080,342),(1169,286),(1252,350),(1360,304),(1360,580),(700,580)],'#4E3554')
 poly(c,[(700,424),(797,371),(896,405),(1003,365),(1134,411),(1255,366),(1360,398),(1360,580),(700,580)],'#292238')
 rect(c,700,445,660,136,'#191723');poly(c,[(1038,437),(1052,437),(1278,581),(800,581)],'#3B3347')
 for j in range(7):
  y=447+j*j*3;w=2+j*1.6;rect(c,1043-w/2,y,w,2+j,ORANGE)
 line(c,[(1038,438),(794,581)],'#8B6A7D',2);line(c,[(1054,438),(1286,581)],'#8B6A7D',2)
 for x,y,s in [(764,523,1.5),(1250,510,1.2),(851,451,.65),(1176,448,.6)]:pixelpalm(c,x,y,s)
 # Small low-poly car with warm tail lights.
 poly(c,[(1008,485),(1020,469),(1069,469),(1084,485),(1091,510),(1002,510)],'#0F111C');rect(c,1024,475,39,11,'#655064')
 rect(c,1008,494,15,5,ORANGE);rect(c,1070,494,15,5,ORANGE);rect(c,1034,501,24,3,'#736375')
 rect(c,700,564,660,17,BG)
 for x in range(710,1360,12):rect(c,x,564,4,17,'#282335')
def hero(c):
 rect(c,0,0,1400,660,BG);text(c,'ANRHANGELS  /  LINUX RP SERIES',42,37,13,MUTED,'Nimbus Mono PS');text(c,'INSTALL RECORD  01',1145,37,13,ORANGE,'Nimbus Mono PS');line(c,[(42,57),(1358,57)],'#40344A')
 scene(c)
 text(c,'АРИЗОНА',42,178,102,INK,'Nimbus Sans Narrow',True);text(c,'НА LINUX.',42,279,102,ORANGE,'Nimbus Sans Narrow',True)
 rect(c,44,315,35,3,ORANGE);text(c,'Твой маршрут в Arizona RP.',42,362,27,INK)
 text(c,'Официальный клиент. Собранное окружение.',42,408,20,MUTED);text(c,'Проверенные настройки. Свой маршрут домой.',42,438,20,MUTED)
 for x,title,desc in [(43,'01 / ПОДГОТОВИТЬ','Flatpak + Faugus'),(270,'02 / НАСТРОИТЬ','Proton + шрифты'),(490,'03 / ИГРАТЬ','Лаунчер + игра')]:
  text(c,title,x,519,12,ORANGE,'Nimbus Mono PS');text(c,desc,x,547,18,INK)
 line(c,[(42,595),(1358,595)],'#40344A');text(c,'ARIZONA RP  ×  GE-PROTON  ×  FAUGUS',42,632,14,MUTED,'Nimbus Mono PS');text(c,'РУССКИЕ ИНСТРУКЦИИ / ОТКРЫТЫЙ КОД',943,632,13,MUTED,'Nimbus Mono PS')
def route(c):
 rect(c,0,0,1400,290,BG);text(c,'КАРТА МАРШРУТА',35,42,17,ORANGE,'Nimbus Mono PS');text(c,'От чистого окружения до первого входа.',35,77,24)
 for i,(name,desc) in enumerate([('СИСТЕМА','Flatpak · шрифты'),('ОКРУЖЕНИЕ','Faugus · Proton · UMU'),('ЛАУНЧЕР','Официальный EXE'),('ТВОЙ СЕРВЕР','Загрузка клиента · вход')]):
  x=48+i*344;line(c,[(x+16,134),(min(1362,x+344),134)],'#4A3A56',2);circle(c,x+12,134,12,ORANGE if i<3 else TEAL);text(c,str(i+1),x+7,139,14,BG,'Nimbus Mono PS',True)
  text(c,name,x,186,22,INK,'Nimbus Sans Narrow',True);text(c,desc,x,221,16,MUTED)
 text(c,'Скрипт готовит окружение. Официальный лаунчер загружает игру. В аккаунт входишь ты.',35,267,15,MUTED)
def fonts(c):
 rect(c,0,0,1400,315,BG);text(c,'ЧИТАЕТСЯ. ВИДНО. ПОНЯТНО.',36,52,33,INK,'Nimbus Sans Narrow',True)
 text(c,'ШРИФТЫ / КИРИЛЛИЦА / ЭМОДЗИ',36,85,14,ORANGE,'Nimbus Mono PS')
 for x,label,sample,co in [(36,'КИРИЛЛИЦА','Привет, мир.',LILAC),(497,'ЛАТИНИЦА','Welcome home.',ORANGE),(958,'ЭМОДЗИ','',TEAL)]:
  rect(c,x,115,407,148,'#201C2C');text(c,label,x+19,145,12,co,'Nimbus Mono PS');text(c,sample,x+19,213,34,INK,'Nimbus Sans',True)
 # Smiley and heart, vector-native assets instead of platform-dependent emoji fonts.
 circle(c,1020,205,29,TEAL);circle(c,1011,199,3,BG);circle(c,1029,199,3,BG)
 col(c,BG);c.set_line_width(3);c.arc(1020,203,14,.25,math.pi-.25);c.stroke()
 poly(c,[(1091,190),(1098,183),(1110,183),(1117,191),(1125,183),(1137,183),(1144,190),(1144,203),(1117,229),(1091,203)],ORANGE)
 text(c,'Noto / Segoe',1170,211,17,MUTED)
 text(c,'Графическая схема компонентов; не скриншот игрового интерфейса.',36,298,13,MUTED)
for name,width,height,fn in [('hero',1400,660,hero),('route',1400,290,route),('fonts',1400,315,fonts)]:
 for fmt in ['svg','png']:
  surface=cairo.SVGSurface(str(P/f'{name}.svg'),width,height) if fmt=='svg' else cairo.ImageSurface(cairo.FORMAT_RGB24,width,height)
  fn(cairo.Context(surface))
  if fmt=='png':surface.write_to_png(str(P/f'{name}.png'))
  surface.finish()
print('Original illustrations rendered: hero, route, fonts')
