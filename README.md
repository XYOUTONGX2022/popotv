# 电视直播源

`playable.m3u` 是央视与卫视频道列表，同一频道保留多条线路。播放器可订阅此文件的 GitHub Raw 地址。

`movies.m3u` 是独立的经典电影测试列表，条目来自 [PublicDomainM3U](https://github.com/OnlineM3U/publicdomainm3u)，包含影片和海报地址。它是一次性筛选的快照，尚未设置自动更新；部分播放地址或海报可能失效。能否按电影分类显示取决于播放器。

`vod-sources.json` 是按 LibreTV-SourceList 格式整理的第三方电影和综艺点播接口目录。支持该订阅格式的 LibreTV 版本可以导入，其他播放器可手动添加其中的接口；接口内容由源站更新，接口地址失效后不会自动更换。不同 LibreTV 客户端的导入方式可能不同。

`vod.m3u` 是电影和综艺的独立 M3U 列表，使用封面及电影、综艺分组，综艺只列出所选的一期。独立的 GitHub Actions 任务计划每天北京时间约 09:37 重新采集、检查并更新；数量过少时保留上一版。每次检测只证明当时短时可读并能解码一帧，不保证在电视上的网络环境中可播。播放器可能将点播条目放到直播频道列表。

GitHub Actions 每天北京时间约 06:17 采集上游 M3U、两次检查媒体数据、尝试解码视频帧并复查；筛选结果达到最低覆盖要求后才覆盖旧文件。也可在 Actions 手动运行。检测在 GitHub 服务器上进行，不保证同一条线路在家中网络可用或长期稳定；GitHub 的定时任务可能延迟，长时间没有仓库活动时可能暂停。

直播源来源：[IPTV-Collector](https://github.com/Chaniug/IPTV-Collector)、[peterHchina/iptv](https://github.com/peterHchina/iptv)、[best-fan/iptv-sources](https://github.com/best-fan/iptv-sources)、[iptv-org](https://github.com/iptv-org/iptv)、[ChinaIPTV](https://github.com/hujingguang/ChinaIPTV)。线路由第三方提供，请自行确认观看权限。
