# 笑脸报到核心模块包
# 各子模块将在后续步骤中逐步实现：
#   config.py     —— 全局配置
#   camera.py     —— 摄像头采集（手机 IP Webcam / 本地 USB）
#   recognizer.py —— insightface 人脸检测与特征提取
#   gallery.py    —— 底册扫描建库与特征缓存
#   matcher.py    —— 分级匹配（先班级→再年级→失败）与去重
#   voice.py      —— 语音播报（签到成功）
#   exporter.py   —— Excel 结果导出
