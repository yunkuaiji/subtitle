#!/bin/env python
# -*- coding: utf8 -*-
import hashlib
import os
import requests
import sys
import mimetypes
import threading
import argparse
import tempfile
import shutil
# import urllib3
# urllib3.disable_warnings()
from guessit import guessit
from core import SubHDDownloader
DOWNLOADER = SubHDDownloader()
import time
from pymediainfo import MediaInfo
from sanitizer import set_utf8_without_bom
from compressor import ZIPFileHandler, RARFileHandler
# import magic
COMPRESSPR_HANDLER = {
    'rar': RARFileHandler,
    'zip': ZIPFileHandler
}

GetRequest = requests.get
PostRequest = requests.post

POST_URL = 'https://www.shooter.cn/api/subapi.php'

FIND_SUBS = 0  # 找到的字幕数
SUCCESSED_SUBS = 0  # 下载成功的字幕数
FAILED_SUBS = 0  # 下载失败的字幕数
NO_SUBTITLES = []  # 没有找到字幕的文件列表

LOCK_FOR_PRINT = threading.Lock()  # 用于保护print信息时不会出现"乱码"
# (i.e 多行信息出现在同一行)
LOCK_FOR_NO_SUBTITLES = threading.Lock()
LOCK_FOR_FIND = threading.Lock()
LOCK_FOR_SUCCESSED = threading.Lock()
LOCK_FOR_FAILED = threading.Lock()
video_file_extensions = ('.avi', '.rmvb', '.rm', '.asf', '.divx', '.mpg', '.mpeg', '.wmv', '.mp4', '.mkv', '.iso', '.m2ts', '.ts')




class LanguageError(Exception):
    def __init__(self, msg, *args):
        self.msg = msg
        self.args = args

    def __str__(self):
        return '<LanguageError>: Language must be "Eng" or "Chn".' + \
               'Not %s' % self.msg


class TooManyThreadsError(Exception):
    def __init__(self, threads, max_threads):
        self.threads = threads
        self.max_threads = max_threads

    def __str__(self):
        msg = '<TooManyThreadsError>: Too many thrads,' + \
              'maximum threads is {}, you specify {}'
        return msg.format(self.max_threads, self.threads)


def getFileSize(filestring_or_fileobj):
    '''return file size in bytes
    '''
    if isinstance(filestring_or_fileobj, basestring):
        file_stat = os.stat(filestring_or_fileobj)
        return file_stat.st_size
    stat = os.fstat(filestring_or_fileobj.fileno())
    return stat.st_size


def computerVideoHash(videofile):
    seek_positions = [None] * 4
    hash_result = []
    with open(videofile, 'rb') as fp:
        total_size = getFileSize(fp)
        seek_positions[0] = 4096
        seek_positions[1] = total_size / 3 * 2
        seek_positions[2] = total_size / 3
        seek_positions[3] = total_size - 8192
        for pos in seek_positions:
            fp.seek(pos, 0)
            data = fp.read(4096)
            m = hashlib.md5(data)
            hash_result.append(m.hexdigest())
        return ';'.join(hash_result)


def getVideoFileFromDir(dir, recursive=False):
    '''从某一目录中获取所有视频文件，返回basename
    '''
    result = []
    quit_path = "xxxxxx"
    append = result.append
    if recursive:  # 查找目录的目录
        for root, dirs, files in os.walk(dir):
            # 用来遍历目录下的文件和子目录,该函数会返回3个元组（父目录，子目录，文件名）
            if 'BDMV' in dirs:
                print "发现 BDMV 目录:", root
                video_path = root
                downloadbdmvsubtitle(video_path)
                continue
            if root.find(quit_path) >= 0:
                continue
            for filename in files:
                if root.find('BDMV') > 0:
                    continue
                if root.find('BDMV') == -1:
                    f = os.path.abspath(os.path.join(root, filename))
                    # types = mimetypes.guess_type(f)
                    # mtype = types[0]
                    if filename.endswith(video_file_extensions):
                        print "发现视频文件，添加到射手网自动下载列表：", f
                        append(f)
    else:
        for f in os.listdir(dir):  # 只查找单一目录 返回指定的文件夹包含的文件或文件夹的名字的列表
            if os.path.isfile(os.path.join(dir, f)):
                print os.path.join(dir, f)
                if f.endswith(video_file_extensions):
                    print "发现视频文件，添加到射手网自动下载列表：", f
                    #append(f)
                    append(os.path.abspath(os.path.join(dir, f)))
            elif os.path.isdir(os.path.join(dir, f)) and f == 'BDMV':
                print "发现 BDMV 目录:", os.path.join(dir, f)
                downloadbdmvsubtitle(dir)

    return result

def downloadbdmvsubtitle(path):
    filemap = {}
    size = 0
    dir = path
    # 遍历filePath下的文件、文件夹（包括子目录）,查找最大视频文件
    for parent, dirnames, filenames in os.walk(dir):
        for filename in filenames:
            #print('parent is %s, filename is %s' % (parent, filename))
            #print('the full name of the file is %s' % os.path.join(parent, filename))
            size = os.path.getsize(os.path.join(parent, filename))
            filemap.setdefault(os.path.join(parent, filename), size)

    max_file = sorted(filemap.items(), key=lambda filemap: filemap[1], reverse=True)[0]
    #print max_file
    languages = ['Chn', 'Eng']
    video_file = max_file[0]
    output_path = dir+"\BDMV"
    downloadOneSub(video_file, output_path, languages)

def getSubInfo(videofile, lang):
    '''\
    @param videofile: The absolute path of video file
    @param lang: The subtitle's language, it's must be 'Chn' or 'Eng'
    '''
    filehash = computerVideoHash(videofile)
    pathinfo = os.path.basename(videofile)
    format = 'json'
    if lang not in ('Chn', 'Eng'):
        raise LanguageError(lang)

    payload = {'filehash': filehash,
               'pathinfo': pathinfo,
               'format': format,
               'lang': lang}
    res = PostRequest(POST_URL, data=payload)
    if res.content == '\xff':
        return []
    return res.json()


def downloadSubFromSubinfoList(sub_info_list, basename, lang, output):
    '''\
    @param sub_info_list: It's a list of sub_info, 
        the detail infomation about data structure of sub_info can find on
        <https://docs.google.com/document/d/1ufdzy6jbornkXxsD-OGl3kgWa4P9WO5
        NZb6_QYZiGI0/preview>
    @oaram basename: video file's basename(no ext).
    @param lang: language of subtitles
    @param output: The output directory of subtitles
    '''
    global FAILED_SUBS
    global SUCCESSED_SUBS
    counters = {'sub': 0, 'idx': 0, 'srt': 0, 'ass': 0}
    for sub_info in sub_info_list:  #某一种语言的字幕列表
        subfiles = sub_info['Files'] #其中一个字幕 {u'Delay': 0, u'Files': [{u'Ext': u'srt', u'Link': u'https://www.shooter.cn/api/subapi.php?fetch=MTQ2MjYyMjk0OHxpVTlTdloxb0p6NkMydnhhT
        delay = sub_info['Delay']
        desc = sub_info['Desc']
        for subfile in subfiles:
            ext = subfile['Ext']
            link = subfile['Link']
            try:
                res = GetRequest(link)
                if res.status_code == requests.codes.ok:
                    counter = counters.setdefault(ext, 0)
                    counter += 1
                    #print "counter",counter
                    if counter == 3:  #每种语言字幕只下载2个
                        continue
                    counters[ext] = counter
                    n = '' if counters[ext] == 1 else counters[ext] - 1
                    subfilename = '{basename}.{lang}{counter}.{ext}'.format(
                        basename=basename,
                        lang=lang.lower(),
                        counter=n,
                        ext=ext)
                    LOCK_FOR_PRINT.acquire()
                    print '%s' % subfilename
                    LOCK_FOR_PRINT.release()
                    if not os.path.exists(output):
                        os.makedirs(output)
                    subtitle_content = set_utf8_without_bom(res.content)  # Plain string
                    with open(os.path.join(output, subfilename), 'wb') as fp:
                        # print res.content
                        fp.write(subtitle_content)
                else:
                    res.raise_for_status()
                    LOCK_FOR_FAILED.acquire()
                    FAILED_SUBS += 1
                    LOCK_FOR_FAILED.release()
            except requests.exceptions.RequestException as e:
                LOCK_FOR_FAILED.acquire()
                FAILED_SUBS += 1
                LOCK_FOR_FAILED.release()
                print e
    LOCK_FOR_SUCCESSED.acquire()
    SUCCESSED_SUBS += sum(counters.values())
    LOCK_FOR_SUCCESSED.release()


class DownloadSubThread(threading.Thread):
    def __init__(self, root, files, output=None, languages=['Chn', 'Eng']):
        '''\
        @param root: The root path
        @param files: 视频文件名列表(绝对路径)
        @param output: The output directory that downloading subtitles
            will saving in. default is None, it's same as file's dirname
        '''
        self.root = root
        self.files = files
        self.output = output
        self.languages = languages
        self.session = requests.Session()
        threading.Thread.__init__(self)

    def run(self):
        global FIND_SUBS
        global NO_SUBTITLES
        for f in self.files:
            flag = 0
            for lang in self.languages:
                sub_info_list = getSubInfo(f, lang)
                if sub_info_list:
                    LOCK_FOR_FIND.acquire()
                    # The total number of subtitles
                    N = sum([len(sub_info['Files']) for sub_info in sub_info_list])
                    FIND_SUBS += N
                    LOCK_FOR_FIND.release()
                    # get file's basename(and not endswith ext),
                    # it will use to combining subtitle's filename
                    basename = os.path.splitext(os.path.basename(f))[0]
                    if not self.output:
                        # if self.output is None, then the output directory of 
                        # subtitles is same as file's os.path.dirname(file)
                        output = os.path.dirname(f)
                    else:
                        relpath = os.path.relpath(os.path.dirname(f), self.root)
                        output = os.path.join(self.output, relpath)
                    if 'BDMV' in output:
                        basename = 'index'
                    downloadSubFromSubinfoList(sub_info_list, basename, lang, output)
                else:
                    flag += 1
            if flag == len(self.languages):
                # if flag == len(self.languages), that's means
                # can't find video's subtitle. 
                LOCK_FOR_NO_SUBTITLES.acquire()
                NO_SUBTITLES.append(f)
                LOCK_FOR_NO_SUBTITLES.release()


def downloadOneSub(videofile, output=None, languages=['Chn', 'Eng']):
    videofile = os.path.abspath(videofile)
    if videofile.endswith(video_file_extensions):
        # 下载一个字幕
        print '找到 1 个视频文件\n'
        print '*' * 80
        root = os.path.dirname(videofile)
        if output is None:
            output = root
        t = DownloadSubThread(root, [videofile], output, languages)
        t.start()
        t.join()
    else:
        print '%s is not a video file' % args.path
        sys.exit(1)


def downloadManySubs(path, output=None, num_threads=None, languages=['Chn', 'Eng'],
                     recursive=False, compress=False):
    if compress:
        # 如果指定要压缩字幕，则创建一个临时目录，将下载的字幕全部保存到临时目录
        # 最后再进行压缩
        temp_output = tempfile.mkdtemp(prefix='tmp_subtitles')
    videofiles = list(getVideoFileFromDir(path, recursive))
    threads = (len(videofiles) / 2)
    if threads == 0:
        threads = 1
    if num_threads:
        # 如果线程数超过总的文件数目,则触发异常
        if num_threads > len(videofiles):
            raise TooManyThreadsError(num_threads, len(videofiles))
        threads = num_threads
    # 打印信息
    print '找到 %s 视频文件\n' % len(videofiles)
    print '*' * 80
    task_size, remainder = divmod(len(videofiles), threads)
    tasks = []
    for i in range(threads):
        task = videofiles[i * task_size: (i + 1) * task_size]
        tasks.append(task)
    # 将无法均匀分配的任务全部分配给最后一个线程
    if remainder > 0:
        tasks[-1].extend(videofiles[-remainder:])
    thread_list = []
    for task in tasks:
        if compress:
            t = DownloadSubThread(path, task, temp_output, languages)
        else:
            t = DownloadSubThread(path, task, output, languages)
        thread_list.append(t)
    [t.start() for t in thread_list]
    [t.join() for t in thread_list]
    if compress:
        zipname = 'subtitles'
        if not output:
            output = path
        shutil.make_archive(os.path.join(output, zipname), 'zip', temp_output)
        shutil.rmtree(temp_output)
        print '*' * 80
        print 'subtitles.zip saving in %s' % os.path.join(output, zipname)

def get_subtitle(keyword, is_filename=True, auto_download=False,
                 chiconv_type='zht', out_file=None):
    '''The main function of the program.

    Args:
        keyword: the keyword to query, either as filename or raw string.
        is_filename: boolean value indicates the keyword is filename or not.
        auto_download: skip all interactive query if it's turn on
        chiconv_type: either 'zhs' or 'zht'
        out_file: optional, the destination path of subtitle.

    Returns:
    '''
    subtitle = {} # record for subtitle
    if is_filename:
        filename = keyword
        keyword = get_guessed_video_name(filename)

    results = DOWNLOADER.search(keyword)
    if not results:
        print "No subtitle for %s" % keyword
        return subtitle

    if not auto_download:
        target = choose_subtitle(results)
    else:
        target = results[0]

    # Download sub here.
    datatype, sub_data = DOWNLOADER.download(target.get('id'))
    file_handler = COMPRESSPR_HANDLER.get(datatype)
    compressor = file_handler(sub_data)

    try:
        subtitle['name'], subtitle['body'] = compressor.extract_bestguess()
        subtitle['name'] = './' + subtitle['name'].split('/')[-1]
        subtitle['extension'] = subtitle['name'].split('.')[-1]
    except ValueError:
        print '错误，无法解压字幕文件,可能非压缩文件'

    #if subtitle['extension'] == 'srt':
     #   subtitle['body'] = reset_index(subtitle['body'])
    #if subtitle['extension'] != 'sub':
     #   subtitle['body'] = set_utf8_without_bom(subtitle['body']) # Plain string
     #   subtitle['body'] = subtitle['body'].replace('\r\n', '\n') # Unix-style line endings

    return subtitle

def choose_subtitle(candidates):
    '''Console output for choosing subtitle.

    Args:
        candidates: A list of dictionaries of subtitles.
    Returns:
        candidate: One dictionary within the list.

    '''
    indexes = range(len(candidates))
    for i in indexes:
        item = candidates[i]
        print '%s) %s (%s)' % (i+1, item.get('title'), item.get('org'))
    choice = None
    while not choice:
        try:
            choice = int(raw_input("Select one subtitle to download: "), 10)
        except ValueError:
            print 'Error: only numbers accepted'
            continue
        if not choice - 1 in indexes:
            print 'Error: numbers not within the range'
            choice = None
    candidate = candidates[choice - 1]
    return candidate

def get_guessed_video_name(video_name):
    '''Parse the video info from the filename

    Args:
        video_name: the filename of the video
    Returns:
        keyword: return video title, usually as movie name,
                 otherwise the series title, usually as drama name.

    '''
    video_info = guessit(video_name)
    print video_info
    if video_info.get('type') == 'episode':
        title = video_info.get('title')
        season = video_info.get('season')
        episode = video_info.get('episode')
        if title and season and episode:
            search_string = "%s S%.2dE%.2d" % (title, season, episode,)
            print search_string
            return search_string
        else:
            return video_info.get('title') or video_info.get('series')
    else:
        return video_info.get('title') or video_info.get('series')



def main(path, output=None, num_threads=None, languages=['Chn', 'Eng'],
         recursive=False, compress=False):
    if os.path.exists(path):
        if os.path.isfile(path):
            downloadOneSub(path, output, languages)

        elif os.path.isdir(path):
            downloadManySubs(path, output, num_threads, languages, recursive, compress)
        else:
            print '%s is neither a directory nor a file' % path
            sys.exit(1)

        print '*' * 80
        tmp = 'Finish.find {} subtitles,{} sucessed,{} failed,' + \
              '{} files not found subtitle'
        print tmp.format(FIND_SUBS, SUCCESSED_SUBS, FAILED_SUBS,
                         len(NO_SUBTITLES))
        if NO_SUBTITLES:
            print u"以下%s个文件无法从射手网自动下载字幕，将转subhd手动下载：" % len(NO_SUBTITLES)
            for f in NO_SUBTITLES:
                print f
            if raw_input(u"按任意键开始subhd手动下载字幕："):
                pass
            for f in NO_SUBTITLES:
                print f
                if 'BDMV' in f:
                    # Y:\TDDOWNLOAD\Spectre.2015.1080p.BluRay.AVC.DTS-HD.MA.7.1-RARBG\BDMV\STREAM
                    print os.path.basename(os.path.split(f)[0].replace("\BDMV\STREAM", ""))
                    video_path = os.path.basename(os.path.split(f)[0].replace("\BDMV\STREAM", ""))
                    #os.path.split(f)[0]
                    sub_content = get_subtitle(video_path, is_filename=True, auto_download=False, chiconv_type='zhs', out_file=None)
                    if sub_content:
                        if sub_content['extension'] != 'sub':
                            subtitle_content = set_utf8_without_bom(sub_content['body'])
                        else:
                            subtitle_content = sub_content['body']
                        with open(os.path.join(os.path.split(f)[0].replace("\STREAM", ""), "index."+sub_content['extension']), 'wb') as fp:
                            # print res.content
                            fp.write(subtitle_content)
                else:
                    print '  %s' % os.path.basename(f)
                    sub_content = get_subtitle(os.path.basename(f), is_filename=True, auto_download=False, chiconv_type='zhs', out_file=None)
                    if sub_content:
                        if sub_content['extension'] != 'sub':
                            subtitle_content = set_utf8_without_bom(sub_content['body'])
                        else:
                            subtitle_content = sub_content['body']
                        basename = os.path.splitext(os.path.basename(f))[0]+"."+sub_content['extension']
                        with open(os.path.join(os.path.split(f)[0], basename), 'wb') as fp:
                            # print res.content
                            fp.write(subtitle_content)

    else:
        # The path doesn't exists.
        print '%s Not exists.' % path
        sys.exit(1)



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('path', help="The directory contains vedio files")
    parser.add_argument('-o', '--output', help="The output directory of subtitles")
    parser.add_argument('-c', '--compress', action='store_true', default=False,
                        help="Whether compress subtitles, only effective " + \
                             "when argument <path> is a directory")
    parser.add_argument('-n', '--threads', type=int, help="specify number of threads")
    parser.add_argument('-r', '-R', '--recursive', action='store_true',
                        default=False, help="whether recursive directory")
    parser.add_argument('--lang', choices=['Chn', 'Eng'], dest='languages',
                        nargs=1, default=['Chn', 'Eng'],
                        help="chice the language of subtitles, it only can be" + \
                             "'Chn' or 'Eng', if not given, default choose both two")

    args = parser.parse_args()
    path = args.path
    output = args.output
    compress = args.compress
    threads = args.threads
    recursive = args.recursive
    languages = args.languages
    # print args
    main(path, output, threads, languages, recursive, compress)
