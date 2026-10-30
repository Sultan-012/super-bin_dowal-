"""Arabic PDF and UTF-8 BOM CSV exports rendered from database report values.

Windows uses arabic-reshaper/python-bidi. A system FriBidi fallback supports
offline Linux QA without weakening or replacing the database implementation.
"""
import csv
import ctypes
import ctypes.util
import io
import threading
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

FONT_LOCK=threading.Lock()
ASSETS=Path(__file__).parent/'assets'


def rtl(value):
    text=str(value)
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(text),base_dir='R')
    except ImportError:
        library=ctypes.util.find_library('fribidi')
        if not library:
            raise RuntimeError('Install arabic-reshaper and python-bidi for Arabic PDF exports.') from None
        bidi=ctypes.CDLL(library)
        bidi.fribidi_log2vis.argtypes=[ctypes.POINTER(ctypes.c_uint32),ctypes.c_int,
            ctypes.POINTER(ctypes.c_uint32),ctypes.POINTER(ctypes.c_uint32),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p]
        bidi.fribidi_log2vis.restype=ctypes.c_int
        source=(ctypes.c_uint32*len(text))(*map(ord,text))
        output=(ctypes.c_uint32*len(text))()
        direction=ctypes.c_uint32(0x111)
        bidi.fribidi_log2vis(source,len(text),ctypes.byref(direction),output,None,None,None)
        return ''.join(map(chr,output))


def amount(value):
    return '—' if value is None else f'{Decimal(str(value)):,.2f}'


def date_label(value):
    parsed=date.fromisoformat(str(value)[:10])
    months=['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر']
    return f'{parsed.day} {months[parsed.month-1]} {parsed.year}'


class ArabicDocument:
    def __init__(self, title, store):
        with FONT_LOCK:
            if 'BinDoul' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('BinDoul',str(ASSETS/'DejaVuSans.ttf')))
                pdfmetrics.registerFont(TTFont('BinDoulBold',str(ASSETS/'DejaVuSans-Bold.ttf')))
        self.stream=io.BytesIO()
        self.canvas=Canvas(self.stream,pagesize=A4,pageCompression=1)
        self.canvas.setTitle(title)
        self.canvas.setAuthor(store)
        self.title,self.store,self.page=title,store,0
        self.width,self.height=A4
        self.new_page()

    def footer(self):
        c=self.canvas
        c.setStrokeColor(colors.HexColor('#dae3df'))
        c.line(38,43,self.width-38,43)
        c.setFont('BinDoul',8)
        c.setFillColor(colors.HexColor('#53665e'))
        c.drawRightString(self.width-38,28,rtl(self.store+' | ريال يمني'))
        c.drawString(38,28,str(self.page))

    def new_page(self):
        if self.page:
            self.footer()
            self.canvas.showPage()
        self.page+=1
        c=self.canvas
        c.setFillColor(colors.HexColor('#163f35'))
        c.rect(0,self.height-105,self.width,105,fill=1,stroke=0)
        c.setFillColor(colors.white)
        c.setFont('BinDoulBold',17)
        c.drawRightString(self.width-38,self.height-39,rtl(self.store))
        c.setFont('BinDoul',11)
        c.drawRightString(self.width-38,self.height-65,rtl(self.title))
        c.setFont('BinDoul',8)
        c.drawString(38,self.height-87,'YER')
        self.y=self.height-128

    def ensure(self,height=24):
        if self.y-height<64:
            self.new_page()

    def text(self,text,size=10,bold=False):
        font='BinDoulBold' if bold else 'BinDoul'
        for paragraph in str(text).splitlines() or ['']:
            words=paragraph.split()
            lines=[]
            current=''
            for word in words:
                # Split extremely long unbroken identifiers rather than clipping.
                pieces=[word[i:i+55] for i in range(0,len(word),55)]
                for piece in pieces:
                    candidate=(current+' '+piece).strip()
                    if current and pdfmetrics.stringWidth(rtl(candidate),font,size)>self.width-76:
                        lines.append(current)
                        current=piece
                    else:
                        current=candidate
            lines.append(current)
            for line in lines:
                self.ensure(size+9)
                self.canvas.setFillColor(colors.HexColor('#253f34'))
                self.canvas.setFont(font,size)
                self.canvas.drawRightString(self.width-38,self.y,rtl(line))
                self.y-=size+9

    def section(self,title):
        self.ensure(48)
        self.y-=9
        self.text(title,12,True)
        self.canvas.setStrokeColor(colors.HexColor('#dce5e0'))
        self.canvas.line(38,self.y+6,self.width-38,self.y+6)
        self.y-=8

    def metric(self,label,value):
        self.ensure(29)
        self.canvas.setFillColor(colors.HexColor('#edf3ef'))
        self.canvas.rect(38,self.y-8,self.width-76,27,fill=1,stroke=0)
        self.canvas.setFillColor(colors.HexColor('#263f34'))
        self.canvas.setFont('BinDoul',10)
        self.canvas.drawRightString(self.width-47,self.y+1,rtl(label))
        self.canvas.setFont('BinDoulBold',11)
        self.canvas.drawString(47,self.y+1,amount(value))
        self.y-=34

    def bytes(self):
        self.footer()
        self.canvas.save()
        return self.stream.getvalue()


def report_pdf(data):
    """Administrative report only: no shortage/surplus without counted cash."""
    document=ArabicDocument('تقرير الورديات',data['store']['store_name'])
    document.text('سجل الورديات المسلّمة والمُعتمدة إداريًا. العملة: ريال يمني.')
    if data.get('start'):
        document.text('بداية الفترة: '+date_label(data['start'])+' | النهاية (غير مشمولة): '+date_label(data['end_exclusive']))
    totals=data['totals']
    document.text(f"الورديات: {totals['count']} | المعتمدة: {totals['approved']} | غير المعتمدة: {totals['pending']}")
    document.section('ملخص المبالغ المدخلة')
    for label,key in [('إجمالي المبيعات','total_sales'),('مبيعات جهاز المحاسبة','device_sales'),
                      ('المبيعات خارج الجهاز','outside_sales'),('المشتريات','purchases'),
                      ('التحويلات البنكية','shift_bank'),('الإيداعات','deposit_amount')]:
        document.metric(label,totals[key])
    document.text('الاعتماد الجديد هو مراجعة إدارية، ولا تُحسب فروق النقد أو العجز أو الفائض.',8)
    document.section('الورديات')
    for shift in data['shifts']:
        t=shift['totals']
        document.ensure(95)
        document.text(f"وردية #{shift['id']} | {shift['employee']} | {date_label(shift['business_date'])}",10,True)
        document.text('رقم سند الإيداع: '+shift['deposit_number'],9)
        document.text('المبيعات: '+amount(t['total_sales'])+' | الإيداع: '+amount(t['deposit_amount']),9)
        document.text('الحالة: '+('معتمدة' if shift['approved'] else 'بانتظار الاعتماد'),9)
        document.y-=7
    if not data['shifts']:
        document.text('لا توجد ورديات في الفترة المحددة.')
    return document.bytes()


def shift_pdf(detail,store):
    version=detail['version']
    document=ArabicDocument('تفاصيل الوردية #'+str(detail['shift']['id']),store['store_name'])
    document.text(f"الموظف: {detail['employee']} | النسخة: {version['number']}")
    document.text(f"تاريخ الصندوق: {date_label(version['business_date'])} | تاريخ السند: {date_label(version['deposit_date'])}")
    document.text('رقم سند الإيداع: '+version['deposit_number'])
    document.text('الحالة: '+('معتمدة' if detail['approved'] else 'بانتظار اعتماد المدير'))
    document.section('بيانات الوردية')
    for label,key in [('مبيعات الجهاز','device_sales'),('الإيداع','deposit_amount'),
                      ('مبيعات خارج الجهاز','outside_sales'),('المشتريات','purchases'),
                      ('التحويلات البنكية','shift_bank')]:
        document.metric(label,detail['totals'][key])
    labels={'purchase':'فواتير المشتريات','off_device':'الأصناف خارج الجهاز','bank':'التحويلات البنكية'}
    for kind,title in labels.items():
        document.section(title)
        lines=[entry for entry in detail['entries'] if entry['kind']==kind]
        for entry in lines:
            document.ensure(95)
            document.text(entry['name']+' | المبلغ: '+amount(entry['amount']),10,True)
            if entry.get('invoice_number'):
                document.text('رقم الفاتورة: '+entry['invoice_number'])
            if entry.get('item_code'):
                document.text('رقم الصنف: '+entry['item_code']+' | العدد: '+str(entry['quantity']))
            if entry.get('description'):
                document.text('التفاصيل: '+entry['description'])
            if entry.get('reference'):
                document.text('رقم الحوالة: '+entry['reference'])
            document.y-=7
        if not lines:
            document.text('لا توجد عمليات في هذا القسم.')
    document.section('ملاحظات')
    document.text(version.get('notes') or 'لا توجد ملاحظات.')
    if detail.get('approval'):
        document.text('ملاحظة المدير: '+(detail['approval'].get('note') or 'تم الاعتماد.'))
    document.text('الاعتماد الإداري الجديد لا يعني مطابقة النقد أو احتساب العجز والفائض.',8)
    return document.bytes()


def report_csv(data):
    output=io.StringIO(newline='')
    writer=csv.writer(output)
    writer.writerow(['رقم الوردية','الموظف','تاريخ الصندوق','تاريخ سند الإيداع','رقم السند',
                     'إجمالي المبيعات','مبيعات الجهاز','المبيعات خارج الجهاز',
                     'التحويلات البنكية','المشتريات','الإيداع','الحالة'])
    def safe_text(value):
        text=str(value)
        import unicodedata
        index = 0
        while index < len(text) and (text[index].isspace() or unicodedata.category(text[index])[0] == 'C'):
            index += 1
        return "'"+text if text[index:].startswith(('=','+','-','@')) or text.startswith(('\t','\r','\n')) else text
    for shift in data['shifts']:
        t=shift['totals']
        writer.writerow([shift['id'],safe_text(shift['employee']),shift['business_date'],shift['deposit_date'],
                         safe_text(shift['deposit_number']),t['total_sales'],t['device_sales'],t['outside_sales'],
                         t['shift_bank'],t['purchases'],t['deposit_amount'],
                         'معتمدة' if shift['approved'] else 'بانتظار الاعتماد'])
    return ('\ufeff'+output.getvalue()).encode('utf-8')
