# ZhuijuCalendarDiscover (MoviePilot v2)

独立版 `追剧日历探索` 插件，来源于 ForwardWidgets 的“追剧日历”能力移植。

## 目录结构

```text
ZhuijuCalendarDiscover-standalone/
├── package.v2.json
└── plugins.v2/
    └── zhuijucalendardiscover/
        └── __init__.py
```

## 安装方式

### 方式一：作为独立插件仓库安装（推荐）

1. 将本目录内容推送到你自己的 GitHub 仓库根目录。
2. 在 MoviePilot v2 中添加插件仓库地址（`package.v2.json` 的 Raw URL）。
3. 在插件市场搜索并安装 `追剧日历探索`。

> 示例 Raw URL：`https://raw.githubusercontent.com/<用户名>/<仓库名>/<分支>/package.v2.json`

### 方式二：手动覆盖安装

1. 将 `plugins.v2/zhuijucalendardiscover` 目录复制到你的插件仓库 `plugins.v2/` 下。
2. 将 `package.v2.json` 中的 `ZhuijuCalendarDiscover` 条目合并到你的仓库 `package.v2.json`。
3. 重启 MoviePilot 或刷新插件市场。

## 功能

- 今日播出：剧集/番剧/国漫/综艺
- 明日播出：剧集/番剧/国漫/综艺
- 播出周历：类型 + 周几
- 各项榜单：现正热播、人气 Top 10、新剧雷达、热门国漫、已收官好剧、华语热门、本季新番
- 地区榜单：国产剧、日剧、英美剧、番剧、韩剧、港台剧
- 今日推荐

## 说明

- 数据源：`home0/home1` + `gist`（与 ForwardWidgets 追剧日历保持一致）。
- 为减少数据缺失，插件会按需补充 TMDB 详情（依赖 MoviePilot 的 TMDB 配置）。
