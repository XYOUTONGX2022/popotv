# 电视直播源

`playable.m3u` 是央视与卫视频道列表，同一频道保留多条线路。播放器可订阅此文件的 GitHub Raw 地址。

`movies.m3u` 是独立的经典电影测试列表，条目来自 [PublicDomainM3U](https://github.com/OnlineM3U/publicdomainm3u)，包含影片和海报地址。它是一次性筛选的快照，尚未设置自动更新；部分播放地址或海报可能失效。能否按电影分类显示取决于播放器。

GitHub Actions 每天北京时间约 06:17 采集上游 M3U、两次检查媒体数据、尝试解码视频帧并复查；筛选结果达到最低覆盖要求后才覆盖旧文件。也可在 Actions 手动运行。检测在 GitHub 服务器上进行，不保证同一条线路在家中网络可用或长期稳定；GitHub 的定时任务可能延迟，长时间没有仓库活动时可能暂停。

直播源来源：[IPTV-Collector](https://github.com/Chaniug/IPTV-Collector)、[peterHchina/iptv](https://github.com/peterHchina/iptv)、[best-fan/iptv-sources](https://github.com/best-fan/iptv-sources)、[iptv-org](https://github.com/iptv-org/iptv)、[ChinaIPTV](https://github.com/hujingguang/ChinaIPTV)。线路由第三方提供，请自行确认观看权限。
