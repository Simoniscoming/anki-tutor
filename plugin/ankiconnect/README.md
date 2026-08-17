# AnkiConnect 内置快照

- 上游：https://git.sr.ht/~foosoft/anki-connect（GitHub 镜像：https://github.com/FooSoft/AnkiConnect，已归档）
- AnkiWeb ID：`2055492159`
- 许可：GPL v3+（见本目录 LICENSE，随代码一起分发）
- 获取方式：从本机经 AnkiWeb 官方渠道（Get Add-ons 数字码）安装的副本**原样复制**，未做任何代码修改（bootstrap 只在安装后预写 config.json / meta.json 数据文件，不属于修改）
- 获取日期：2026-08-17（对 Anki 26.05 实测通过）
- 快照会过期，但不用担心：安装时文件夹以 AnkiWeb ID 命名并预写 meta.json，Anki 自身的每日插件更新检查会把旧版本自动刷成上游新版
- bootstrap 的来源解析顺序：`--ankiconnect-src`（显式指定）> 本目录 > ankiweb 下载兜底
