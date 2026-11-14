# 电视直播源

`playable.m3u` 是央视与卫视频道列表，同一频道保留多条线路。播放器可订阅此文件的 GitHub Raw 地址。

GitHub Actions 每天北京时间约 06:17 采集上游 M3U、两次检查媒体数据、尝试解码视频帧并复查；筛选结果达到最低覆盖要求后才覆盖旧文件。也可在 Actions 手动运行。检测在 GitHub 服务器上进行，不保证同一条线路在家中网络可用或长期稳定；GitHub 的定时任务可能延迟，长时间没有仓库活动时可能暂停。

来源：[IPTV-Collector](https://github.com/Chaniug/IPTV-Collector)、[peterHchina/iptv](https://github.com/peterHchina/iptv)、[best-fan/iptv-sources](https://github.com/best-fan/iptv-sources)、[iptv-org](https://github.com/iptv-org/iptv)。线路由第三方提供，请自行确认观看权限。
