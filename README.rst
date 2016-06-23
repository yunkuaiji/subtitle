本字幕下載器结合了：

1、用shooter.org提供的api下载字幕  https://github.com/L-xm/python-shooter.org

2、Subhd.py: subhd.com 字幕下載器  https://github.com/pa4373/subhd.py

介绍

1、脚本对射手网提供的查找字幕API进行了简单封装，对视频文件进行字模匹配，然后将匹配到的字幕保存到与视频文件相同的目录。

2、能对MKV,原盘bdmv,iso等视频节目自动查找并下载字幕

3、自动转换字幕为utf-8格式

4、流程为先从射手网查找字幕，找到就自动下载，找不到再从subhd.com查找然后手动选择下载。

5、原盘bdmv：字幕下载并改名为index.srt,放入BDMV文件夹。

6、原盘ISO:将字幕下载并改为和BDISO文件同名。



参数说明


path, 包含视频文件的目录。

-o, --output, 指定字幕保存目录,默认字幕保存在视频文件所在的目录。

-c, --compress, 指定是否要压缩字幕,压缩包放在指定的output目录,如果output没有指定, 则放在path目录下.注意: 对下载单个视频的字幕无效。

-n, --threads, 指定线程数。

-r, --recrusive, 是否递归查找目录下视频文件。默认不递归, 也就是说只下载path目录下视频文件的字幕。

--lang, 选择字幕语言, 可选值有:[Chn, Eng], 默认为[Chn,Eng].

示例


下载单个视频的字幕

#SubFinder.py d:/media/xxx.mp4

下载目录中所有视频的字幕

#SubFinder.py d:/media/directory_contains_video_file

递归下载

#SubFinder.py -r d:/media/directory_contains_video_file

递归下载并压缩打包

#SubFinder.py -r -c d:/media/directory_contains_video_file


