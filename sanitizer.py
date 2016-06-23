#!/bin/env python
# -*- coding: utf8 -*-
'''Few sanitizer functions to process subtitle text.
'''
import chardet
import codecs
#from conv import TongWenConv
import StringIO
import pysrt
from langconv import *

#__TONGWEN = TongWenConv()

def to_unicode(sub_str):
    '''Convert plain string to unicode object.

    Auto encoding converison occurs if the plain string isn't encoded
    in UTF-8.

    Args:
        sub_str: The plain string intended to be converted to unicode
                 object
    Returns:
        sub_unicode: The converted unicode object

    '''
    sub_unicode = sub_str
    encoding = chardet.detect(sub_str).get('encoding')
    if encoding:
        sub_unicode = unicode(sub_str, encoding, 'ignore')
    return sub_unicode

def set_utf8_without_bom(sub_unicode):
    '''Convert a unicode object to plain string.

    Remove BOM header if exists

    Args:
        sub_unicode: any unicode object intended to be converted
                     to string
    Returns:
        sub_str: Plain string encoded in UTF-8 without BOM
    '''

    sub_str = to_unicode(sub_unicode)
    #if sub_str.startswith(u'\ufeff'):
    #    sub_unicode = sub_str[3:]
    try:
        sub_str = sub_str.encode('utf-8')
        # 将繁体转换成简体
        #line = Converter('zh-hans').convert(sub_str.decode('utf-8'))
        #sub_str = line.encode('utf-8')
    except:
        print "不能转换为utf-8格式保存"
    else:
        if sub_str[:3] == codecs.BOM_UTF8:
            sub_str = sub_str[3:]
    finally:
        return sub_str

def reset_index(sub_unicode):
    '''Reset SRT subtitles index.

    The subtitle index increases incrementally from 1.

    Args:
        sub_unicode: unicode object containing SRT subtitles
    Returns:
        new_sub_unicode: Reordered unicode SRT object.

    '''
    subs = pysrt.from_string(sub_unicode)
    for i in range(1, len(subs) + 1):
        subs[i - 1].index = i

    new_sub = StringIO.StringIO()
    subs.write_into(new_sub)
    new_sub_unicode = new_sub.getvalue()
    new_sub.close()
    return new_sub_unicode
