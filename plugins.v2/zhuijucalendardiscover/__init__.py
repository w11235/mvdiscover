import re
from typing import Any, Dict, List, Optional, Tuple

import requests

from app import schemas
from app.core.cache import cached
from app.core.config import settings
from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import DiscoverSourceEventData
from app.schemas.types import ChainEventType

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}

HOME_URLS = {
    "home0": "https://zjrl-1318856176.cos.accelerate.myqcloud.com/home0.json",
    "home1": "https://zjrl-1318856176.cos.accelerate.myqcloud.com/home1.json",
}
GIST_BASE_URL = (
    "https://gist.githubusercontent.com/huangxd-/"
    "5ae61c105b417218b9e5bad7073d2f36/raw"
)

DAY_TITLE_MAP = {
    ("today", "tv"): "今天播出的剧集",
    ("today", "anime"): "今天播出的番剧",
    ("tomorrow", "tv"): "明天播出的剧集",
    ("tomorrow", "anime"): "明天播出的番剧",
}

DAY_GIST_FILE_MAP = {
    ("today", "guoman"): "guoman_today.json",
    ("today", "variety"): "zongyi_today.json",
    ("tomorrow", "guoman"): "guoman_tomorrow.json",
    ("tomorrow", "variety"): "zongyi_tomorrow.json",
}

WEEK_FILE_MAP = {
    "tv": "juji_week.json",
    "anime": "fanju_week.json",
    "guoman": "guoman_week.json",
    "variety": "zongyi_week.json",
}

WEEKDAY_ORDER = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

RANK_TITLE_MAP = {
    "now_playing": "现正热播",
    "top10": "人气 Top 10",
    "new_show": "新剧雷达",
    "hot_guoman": "热门国漫",
    "finished": "已收官好剧",
    "cn_hot": "华语热门",
    "season_anime": "本季新番",
}

AREA_TITLE_MAP = {
    "cn": "国产剧",
    "jp": "日剧",
    "usuk": "英美剧",
    "anime": "番剧",
    "kr": "韩剧",
    "hktw": "港台剧",
}


class ZhuijuCalendarDiscover(_PluginBase):
    # 插件名称
    plugin_name = "追剧日历探索"
    # 插件描述
    plugin_desc = "让探索支持追剧日历的今明播、周历和榜单数据。"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/jxxghp/MoviePilot-Plugins/main/icons/Moviepilot_A.png"
    # 插件版本
    plugin_version = "1.0.0"
    # 插件作者
    plugin_author = "anxian,huangxd"
    # 作者主页
    author_url = "https://github.com/huangxd-/ForwardWidgets"
    # 插件配置项ID前缀
    plugin_config_prefix = "zhuijucalendardiscover_"
    # 加载顺序
    plugin_order = 99
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled = False

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = bool(config.get("enabled"))

        tmdb_image_domain = str(getattr(settings, "TMDB_IMAGE_DOMAIN", "") or "")
        tmdb_image_domain = (
            tmdb_image_domain.replace("https://", "")
            .replace("http://", "")
            .split("/")[0]
        )
        if tmdb_image_domain and tmdb_image_domain not in settings.SECURITY_IMAGE_DOMAINS:
            settings.SECURITY_IMAGE_DOMAINS.append(tmdb_image_domain)

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/zhuiju_calendar_discover",
                "endpoint": self.zhuiju_calendar_discover,
                "methods": ["GET"],
                "summary": "追剧日历探索数据源",
                "description": "获取追剧日历数据",
            }
        ]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用插件",
                                        },
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ], {"enabled": False}

    def get_page(self) -> List[dict]:
        pass

    @cached(region="zhuijucalendar_http", ttl=21600, skip_none=True)
    def __fetch_json(self, url: str) -> Optional[Any]:
        try:
            res = requests.get(url, headers=HEADERS, timeout=20)
            res.raise_for_status()
            return res.json()
        except Exception as err:
            logger.error(f"请求追剧日历数据失败：{url}，错误：{err}")
            return None

    @cached(region="zhuijucalendar_tmdb_detail", ttl=86400, skip_none=True)
    def __fetch_tmdb_detail(
        self, tmdb_id: int, media_type: str = "tv"
    ) -> Optional[Dict[str, Any]]:
        api_domain = getattr(settings, "TMDB_API_DOMAIN", None)
        api_key = getattr(settings, "TMDB_API_KEY", None)
        if not api_domain or not api_key:
            return None

        url = f"https://{api_domain}/3/{media_type}/{tmdb_id}"
        params = {"api_key": api_key, "language": "zh-CN"}
        try:
            res = requests.get(url, params=params, headers=HEADERS, timeout=20)
            if res.ok:
                return res.json()
            params.pop("language", None)
            res = requests.get(url, params=params, headers=HEADERS, timeout=20)
            if res.ok:
                return res.json()
        except Exception as err:
            logger.warning(f"获取TMDB详情失败：{tmdb_id}，错误：{err}")
        return None

    @staticmethod
    def __extract_year(date_text: Any) -> Optional[str]:
        if not date_text:
            return None
        match = re.search(r"(19|20)\d{2}", str(date_text))
        if not match:
            return None
        return match.group(0)

    @staticmethod
    def __to_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @staticmethod
    def __build_poster_url(path: Any) -> Optional[str]:
        if not path:
            return None
        text = str(path)
        if text.startswith("http://") or text.startswith("https://"):
            return text
        if text.startswith("/"):
            return f"https://{settings.TMDB_IMAGE_DOMAIN}/t/p/w500{text}"
        return None

    @staticmethod
    def __normalize_input(value: Optional[str], default: str) -> str:
        return str(value).strip() if value else default

    @staticmethod
    def __build_media_type(is_movie: bool) -> str:
        return "movie" if is_movie else "tv"

    def __normalize_item(
        self, item: dict, default_media_type: str = "tv"
    ) -> Optional[Dict[str, Any]]:
        tmdb_id = item.get("tmdb_id") or item.get("id")
        try:
            tmdb_id = int(tmdb_id)
        except Exception:
            return None

        is_movie = self.__to_bool(item.get("isMovie")) or default_media_type == "movie"
        media_type = self.__build_media_type(is_movie)

        title = item.get("name") or item.get("title")
        release_date = (
            item.get("release_date") or item.get("first_air_date") or item.get("first_aired")
        )
        overview = item.get("overview")
        vote_average = item.get("vote_average")
        poster_path = item.get("poster_path")

        if (not title or not release_date or not overview or not poster_path) and tmdb_id:
            detail = self.__fetch_tmdb_detail(tmdb_id=tmdb_id, media_type=media_type)
            if detail:
                title = title or detail.get("title") or detail.get("name")
                release_date = (
                    release_date or detail.get("release_date") or detail.get("first_air_date")
                )
                overview = overview or detail.get("overview")
                vote_average = (
                    vote_average if vote_average is not None else detail.get("vote_average")
                )
                poster_path = poster_path or detail.get("poster_path")

        if not title:
            return None

        year = self.__extract_year(release_date)
        title_year = f"{title} ({year})" if year else title
        return {
            "type": "电影" if media_type == "movie" else "电视剧",
            "title": title,
            "year": year,
            "title_year": title_year,
            "mediaid_prefix": "tmdb",
            "media_id": str(tmdb_id),
            "poster_path": self.__build_poster_url(poster_path),
            "vote_average": vote_average,
            "overview": overview,
        }

    def __find_home_items(self, home_key: str, title: str) -> List[Dict[str, Any]]:
        data = self.__fetch_json(HOME_URLS[home_key])
        if not isinstance(data, list):
            return []
        for block in data:
            if block.get("title") == title:
                return block.get("content") or []
        return []

    def __load_day_items(self, section: str, category: str) -> List[Dict[str, Any]]:
        gist_file = DAY_GIST_FILE_MAP.get((section, category))
        if gist_file:
            data = self.__fetch_json(f"{GIST_BASE_URL}/{gist_file}")
            return data if isinstance(data, list) else []

        title = DAY_TITLE_MAP.get((section, category))
        if not title:
            return []
        return self.__find_home_items("home1", title)

    def __load_week_items(self, category: str, weekday: str) -> List[Dict[str, Any]]:
        file_name = WEEK_FILE_MAP.get(category)
        if not file_name:
            return []

        data = self.__fetch_json(f"{GIST_BASE_URL}/{file_name}")
        if not isinstance(data, dict):
            return []

        if weekday == "All":
            results: List[Dict[str, Any]] = []
            for key in WEEKDAY_ORDER:
                day_items = data.get(key) or []
                if isinstance(day_items, list):
                    results.extend(day_items)
            return results

        day_items = data.get(weekday) or []
        return day_items if isinstance(day_items, list) else []

    def __load_rank_items(self, rank_type: str) -> List[Dict[str, Any]]:
        title = RANK_TITLE_MAP.get(rank_type)
        if not title:
            return []

        home1_items = self.__find_home_items("home1", title)
        if home1_items:
            return home1_items
        return self.__find_home_items("home0", title)

    def __load_area_items(self, area: str) -> List[Dict[str, Any]]:
        target_title = AREA_TITLE_MAP.get(area)
        if not target_title:
            return []

        data = self.__fetch_json(HOME_URLS["home0"])
        if not isinstance(data, list):
            return []

        for block in data:
            if str(block.get("type")) != "category":
                continue
            area_groups = block.get("content") or []
            for area_group in area_groups:
                if area_group.get("title") == target_title:
                    return area_group.get("data") or []
        return []

    def __load_recommend_items(self) -> List[Dict[str, Any]]:
        data = self.__fetch_json(HOME_URLS["home0"])
        if not isinstance(data, list):
            return []
        for block in data:
            if str(block.get("type")) == "1s":
                return block.get("content") or []
        return []

    def __collect_raw_items(
        self,
        section: str,
        category: str,
        weekday: str,
        rank_type: str,
        area: str,
    ) -> List[Dict[str, Any]]:
        if section in {"today", "tomorrow"}:
            return self.__load_day_items(section=section, category=category)
        if section == "week":
            return self.__load_week_items(category=category, weekday=weekday)
        if section == "rank":
            return self.__load_rank_items(rank_type=rank_type)
        if section == "area":
            return self.__load_area_items(area=area)
        if section == "recommend":
            return self.__load_recommend_items()
        return []

    def zhuiju_calendar_discover(
        self,
        section: str = "today",
        category: str = "tv",
        weekday: str = "All",
        rank_type: str = "now_playing",
        area: str = "cn",
        page: int = 1,
        count: int = 30,
    ) -> List[schemas.MediaInfo]:
        """
        获取追剧日历探索数据
        """
        section = self.__normalize_input(section, "today")
        category = self.__normalize_input(category, "tv")
        weekday = self.__normalize_input(weekday, "All")
        rank_type = self.__normalize_input(rank_type, "now_playing")
        area = self.__normalize_input(area, "cn")

        page = max(1, int(page))
        count = max(1, min(int(count), 100))

        raw_items = self.__collect_raw_items(
            section=section,
            category=category,
            weekday=weekday,
            rank_type=rank_type,
            area=area,
        )
        if not raw_items:
            return []

        start = (page - 1) * count
        end = start + count
        target_items = raw_items[start:end]

        media_infos: List[schemas.MediaInfo] = []
        media_ids = set()
        for item in target_items:
            info = self.__normalize_item(item=item, default_media_type="tv")
            if not info:
                continue
            if info["media_id"] in media_ids:
                continue
            media_ids.add(info["media_id"])
            media_infos.append(schemas.MediaInfo(**info))
        return media_infos

    @staticmethod
    def zhuiju_filter_ui() -> List[dict]:
        def chip(value: str, text: str) -> dict:
            return {
                "component": "VChip",
                "props": {"filter": True, "tile": True, "value": value},
                "text": text,
            }

        return [
            {
                "component": "div",
                "props": {"class": "flex justify-start items-center"},
                "content": [
                    {
                        "component": "div",
                        "props": {"class": "mr-5"},
                        "content": [{"component": "VLabel", "text": "分区"}],
                    },
                    {
                        "component": "VChipGroup",
                        "props": {"model": "section"},
                        "content": [
                            chip("today", "今日播出"),
                            chip("tomorrow", "明日播出"),
                            chip("week", "播出周历"),
                            chip("rank", "各项榜单"),
                            chip("area", "地区榜单"),
                            chip("recommend", "今日推荐"),
                        ],
                    },
                ],
            },
            {
                "component": "div",
                "props": {
                    "class": "flex justify-start items-center",
                    "show": "{{section == 'today' || section == 'tomorrow'}}",
                },
                "content": [
                    {
                        "component": "div",
                        "props": {"class": "mr-5"},
                        "content": [{"component": "VLabel", "text": "类型"}],
                    },
                    {
                        "component": "VChipGroup",
                        "props": {"model": "category"},
                        "content": [
                            chip("tv", "剧集"),
                            chip("anime", "番剧"),
                            chip("guoman", "国漫"),
                            chip("variety", "综艺"),
                        ],
                    },
                ],
            },
            {
                "component": "div",
                "props": {
                    "class": "flex justify-start items-center",
                    "show": "{{section == 'week'}}",
                },
                "content": [
                    {
                        "component": "div",
                        "props": {"class": "mr-5"},
                        "content": [{"component": "VLabel", "text": "类型"}],
                    },
                    {
                        "component": "VChipGroup",
                        "props": {"model": "category"},
                        "content": [
                            chip("tv", "剧集"),
                            chip("anime", "番剧"),
                            chip("guoman", "国漫"),
                            chip("variety", "综艺"),
                        ],
                    },
                ],
            },
            {
                "component": "div",
                "props": {
                    "class": "flex justify-start items-center",
                    "show": "{{section == 'week'}}",
                },
                "content": [
                    {
                        "component": "div",
                        "props": {"class": "mr-5"},
                        "content": [{"component": "VLabel", "text": "周几"}],
                    },
                    {
                        "component": "VChipGroup",
                        "props": {"model": "weekday"},
                        "content": [
                            chip("All", "全部"),
                            chip("Monday", "周一"),
                            chip("Tuesday", "周二"),
                            chip("Wednesday", "周三"),
                            chip("Thursday", "周四"),
                            chip("Friday", "周五"),
                            chip("Saturday", "周六"),
                            chip("Sunday", "周日"),
                        ],
                    },
                ],
            },
            {
                "component": "div",
                "props": {
                    "class": "flex justify-start items-center",
                    "show": "{{section == 'rank'}}",
                },
                "content": [
                    {
                        "component": "div",
                        "props": {"class": "mr-5"},
                        "content": [{"component": "VLabel", "text": "榜单"}],
                    },
                    {
                        "component": "VChipGroup",
                        "props": {"model": "rank_type"},
                        "content": [
                            chip("now_playing", "现正热播"),
                            chip("top10", "人气 Top 10"),
                            chip("new_show", "新剧雷达"),
                            chip("hot_guoman", "热门国漫"),
                            chip("finished", "已收官好剧"),
                            chip("cn_hot", "华语热门"),
                            chip("season_anime", "本季新番"),
                        ],
                    },
                ],
            },
            {
                "component": "div",
                "props": {
                    "class": "flex justify-start items-center",
                    "show": "{{section == 'area'}}",
                },
                "content": [
                    {
                        "component": "div",
                        "props": {"class": "mr-5"},
                        "content": [{"component": "VLabel", "text": "地区"}],
                    },
                    {
                        "component": "VChipGroup",
                        "props": {"model": "area"},
                        "content": [
                            chip("cn", "国产剧"),
                            chip("jp", "日剧"),
                            chip("usuk", "英美剧"),
                            chip("anime", "番剧"),
                            chip("kr", "韩剧"),
                            chip("hktw", "港台剧"),
                        ],
                    },
                ],
            },
        ]

    @eventmanager.register(ChainEventType.DiscoverSource)
    def discover_source(self, event: Event):
        if not self._enabled:
            return
        event_data: DiscoverSourceEventData = event.event_data
        zhuiju_source = schemas.DiscoverMediaSource(
            name="追剧日历",
            mediaid_prefix="tmdb",
            api_path=f"plugin/ZhuijuCalendarDiscover/zhuiju_calendar_discover?apikey={settings.API_TOKEN}",
            filter_params={
                "section": "today",
                "category": "tv",
                "weekday": "All",
                "rank_type": "now_playing",
                "area": "cn",
            },
            depends={
                "category": ["section"],
                "weekday": ["section"],
                "rank_type": ["section"],
                "area": ["section"],
            },
            filter_ui=self.zhuiju_filter_ui(),
        )
        if not event_data.extra_sources:
            event_data.extra_sources = [zhuiju_source]
        else:
            event_data.extra_sources.append(zhuiju_source)

    def stop_service(self):
        pass
