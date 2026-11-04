#!/usr/bin/env python3
"""Original editorial/terminal cards. Rebuild: python3 assets/create_art.py."""
from pathlib import Path
import cairo, math
P=Path(__file__).parent
PROJECT='arizona'
RAD=PROJECT=='radmir'
ACC='#82A492' if RAD else '#D77C60'
PAPER='#F5F1E9';INK='#292824';DARK='#191918';MUT='#8F8B82';BORDER='#D8D1C5'
TITLE='RADMIR' if RAD else 'ARIZONA'
PIX={
'A':['01110','11011','11011','11111','11011','11011','11011'],
'R':['11110','11011','11011','11110','11100','11010','11011'],
'I':['111','010','010','010','010','010','111'],
'Z':['11111','00011','00110','01100','11000','11000','11111'],
'O':['01110','11011','11011','11011','11011','11011','01110'],
'N':['11001','11101','11101','11011','11011','11001','11001'],
'D':['11110','11011','11011','11011','11011','11011','11110'],
'M':['11011','11111','11111','11011','11011','11011','11011'],
'L':['11000','11000','11000','11000','11000','11000','11111'],
'U':['11011','11011','11011','11011','11011','11011','01110'],
'X':['11011','11011','01110','00100','01110','11011','11011'],
'B':['11110','11011','11011','11110','11011','11011','11110']}
def color(c,h):c.set_source_rgb(*(int(h[i:i+2],16)/255 for i in (1,3,5)))
def box(c,x,y,w,h,co,r=0):
 color(c,co)
 if r:
  c.new_sub_path()
  for a,b,ang in [(x+w-r,y+r,-90),(x+w-r,y+h-r,0),(x+r,y+h-r,90),(x+r,y+r,180)]:c.arc(a,b,r,math.radians(ang),math.radians(ang+90))
  c.close_path()
 else:c.rectangle(x,y,w,h)
 c.fill()
def txt(c,s,x,y,z=20,co=INK,font='DejaVu Sans',bold=False):
 c.select_font_face(font,0,cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL);c.set_font_size(z);color(c,co);c.move_to(x,y);c.show_text(s)
def rule(c,x,y,w,co=BORDER):box(c,x,y,w,1,co)
def pixel(c,s,x,y,u=10):
 for letter in s:
  rows=PIX.get(letter)
  if not rows:x+=u*3;continue
  for j,row in enumerate(rows):
   for i,v in enumerate(row):
    if v=='1':
     box(c,x+i*u+2,y+j*u+3,u-1,u-1,'#724B40' if not RAD else '#435C4F')
     box(c,x+i*u,y+j*u,u-1,u-1,ACC)
  x+=(len(rows[0])+1)*u

def fan(c,x,y,scale=1):
 for angle,dx,dy,label in [(-14,-105,20,'SYSTEM'),(13,108,18,'CLIENT'),(0,0,0,'LINUX')]:
  c.save();c.translate(x+dx*scale,y+dy*scale);c.rotate(math.radians(angle));c.scale(scale,scale)
  box(c,-106,-130,212,270,'#10100F',16);box(c,-102,-126,204,262,'#302E2A',14)
  box(c,-80,-101,8,8,ACC,4);txt(c,label,-61,-91,12,'#C6BFB2','DejaVu Sans Mono')
  rule(c,-80,-73,160,'#45423C')
  for yy,ww in [(-43,132),(-20,112),(3,126)]:box(c,-72,yy,ww,7,'#777166',3)
  for xx in [-73,-19,35]:box(c,xx,47,43,43,'#48443D',7)
  box(c,-72,108,142,3,ACC,1);c.restore()
def terminal(c,x,y,w,h):
 box(c,x,y,w,h,DARK,15);box(c,x,y,w,39,'#2A2926',15);box(c,x,y+25,w,14,'#2A2926')
 for i,co in enumerate(['#D77C60','#D3B97B','#82A492']):
  color(c,co);c.arc(x+22+i*20,y+20,5,0,math.tau);c.fill()
 txt(c,'anrhangels / '+PROJECT,x+100,y+25,12,'#AAA398','DejaVu Sans Mono')
def hero(c):
 box(c,0,0,1440,760,PAPER)
 txt(c,'LINUX / RP',48,39,13,INK,'DejaVu Sans Mono',True)
 txt(c,'ANRHANGELS     /     FIELD NOTES  '+('02' if RAD else '01'),968,39,12,MUT,'DejaVu Sans Mono');rule(c,48,60,1344)
 txt(c,'Свой город.',48,131,53,INK,'DejaVu Serif');txt(c,'Своя система.' if RAD else 'Свои правила.',48,193,53,INK,'DejaVu Serif')
 box(c,1196,91,196,35,ACC,17);txt(c,'RADMIR CRMP' if RAD else 'ARIZONA RP',1216,114,14,DARK,'DejaVu Sans Mono',True)
 txt(c,'Установка и настройка на Linux',960,182,19,INK)
 terminal(c,48,231,1344,438)
 txt(c,'$ ./install.sh',80,307,17,'#C2B9A9','DejaVu Sans Mono')
 pixel(c,TITLE,80,339,12 if RAD else 11)
 txt(c,'НА LINUX',81,487,35,PAPER,'DejaVu Sans Mono',True)
 txt(c,'Библиотеки. Музыка. Удобный запуск.' if RAD else 'Лаунчер. Шрифты. Удобный запуск.',81,538,22,'#C0B8AA')
 box(c,81,583,261,39,ACC,5);txt(c,'ИНСТРУКЦИИ + СКРИПТЫ',97,608,14,DARK,'DejaVu Sans Mono',True)
 fan(c,1126,462,.94)
 txt(c,'01 — ПОДГОТОВИТЬ     02 — НАСТРОИТЬ     03 — ЗАПУСТИТЬ',48,717,15,INK,'DejaVu Sans Mono')
 txt(c,'OPEN SOURCE / RU',1200,717,13,MUT,'DejaVu Sans Mono')
def route(c):
 box(c,0,0,1440,410,PAPER);txt(c,'От системы к игре.',42,66,39,INK,'DejaVu Serif')
 txt(c,'ПОРЯДОК УСТАНОВКИ',1120,58,13,MUT,'DejaVu Sans Mono')
 names=[('Система','Flatpak и Faugus','Подготовить окружение'),('Компоненты','Proton и библиотеки','Добавить зависимости'),('Лаунчер','С официального сайта','Загрузить клиент'),('Первый вход','Ваш аккаунт','Запустить игру')]
 for i,(name,sub,desc) in enumerate(names):
  x=42+i*346;box(c,x,103,318,246,'#E9E3D8',10)
  txt(c,'0'+str(i+1),x+22,144,16,ACC,'DejaVu Sans Mono',True);rule(c,x+22,165,274,'#CEC6B8')
  txt(c,name,x+22,212,27,INK,'DejaVu Serif');txt(c,sub,x+22,252,18,INK);txt(c,desc,x+22,317,14,'#706B61')
 txt(c,'СКРИПТ НАСТРАИВАЕТ ОКРУЖЕНИЕ · ОФИЦИАЛЬНЫЙ ЛАУНЧЕР ЗАГРУЖАЕТ ИГРУ',42,387,13,MUT,'DejaVu Sans Mono')
def detail(c):
 box(c,0,0,1440,460,DARK)
 txt(c,'Детали имеют значение.',42,67,39,PAPER,'DejaVu Serif')
 txt(c,'RADMIR / КОМПОНЕНТЫ' if RAD else 'ARIZONA / ТИПОГРАФИКА',42,103,13,ACC,'DejaVu Sans Mono')
 cards=[('01 / ГРАФИКА','Новая графика','UCRT · D3DX9 · D3DCompiler'),('02 / МУЗЫКА','Кириллица в URL','Помощник на время игры'),('03 / ЗАПУСК','radmir','Одна команда для лаунчера')] if RAD else [('01 / ТЕКСТ','Привет, мир.','Кириллица и латиница'),('02 / ШРИФТЫ','Aa Бб 123','DejaVu · опционально Segoe UI'),('03 / СИМВОЛЫ',':)  ♥  ★','Noto Color Emoji')]
 for i,(label,sample,desc) in enumerate(cards):
  x=42+i*459;box(c,x,143,437,244,'#2C2A26',12);txt(c,label,x+24,181,13,ACC,'DejaVu Sans Mono')
  rule(c,x+24,202,389,'#47433C');txt(c,sample,x+24,269,34,PAPER,'DejaVu Serif')
  txt(c,desc,x+24,352,15,'#B5AC9D')
 txt(c,'КОМПОНЕНТЫ И НАСТРОЙКИ ОПИСАНЫ В ДОКУМЕНТАЦИИ',42,431,13,'#9B9386','DejaVu Sans Mono')
for name,w,h,fn in [('hero',1440,760,hero),('route',1440,410,route),('fixes' if RAD else 'fonts',1440,460,detail)]:
 for ext in ['svg','png']:
  s=cairo.SVGSurface(str(P/(name+'.svg')),w,h) if ext=='svg' else cairo.ImageSurface(cairo.FORMAT_ARGB32,w,h)
  fn(cairo.Context(s))
  if ext=='png':s.write_to_png(str(P/(name+'.png')))
  s.finish()
