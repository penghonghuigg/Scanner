# ruff: noqa: E501

from typing import Final

SOURCE_TYPE_NAMES: Final[dict[str, str]] = {
    "OUTSIDE_PROVINCE": "外省流入",
    "UNKNOWN": "来源不详",
    "LOCAL_HUAINAN": "市内串码",
    "ANHUI_OTHER_CITY": "省内市外",
}

_REGION_TEXT: Final[tuple[tuple[str, str], ...]] = (
    ("北京市", "北京市"),
    ("天津市", "天津市"),
    ("上海市", "上海市"),
    ("重庆市", "重庆市"),
    ("台湾省", "台湾省"),
    ("河北省", "石家庄市、唐山市、秦皇岛市、邯郸市、邢台市、保定市、张家口市、承德市、沧州市、廊坊市、衡水市"),
    ("山西省", "太原市、大同市、阳泉市、长治市、晋城市、朔州市、晋中市、运城市、忻州市、临汾市、吕梁市"),
    ("内蒙古自治区", "呼和浩特市、包头市、乌海市、赤峰市、通辽市、鄂尔多斯市、呼伦贝尔市、巴彦淖尔市、乌兰察布市、兴安盟、锡林郭勒盟、阿拉善盟"),
    ("辽宁省", "沈阳市、大连市、鞍山市、抚顺市、本溪市、丹东市、锦州市、营口市、阜新市、辽阳市、盘锦市、铁岭市、朝阳市、葫芦岛市"),
    ("吉林省", "长春市、吉林市、四平市、辽源市、通化市、白山市、松原市、白城市、延边朝鲜族自治州"),
    ("黑龙江省", "哈尔滨市、齐齐哈尔市、鸡西市、鹤岗市、双鸭山市、大庆市、伊春市、佳木斯市、七台河市、牡丹江市、黑河市、绥化市、大兴安岭地区"),
    ("江苏省", "南京市、无锡市、徐州市、常州市、苏州市、南通市、连云港市、淮安市、盐城市、扬州市、镇江市、泰州市、宿迁市"),
    ("浙江省", "杭州市、宁波市、温州市、嘉兴市、湖州市、绍兴市、金华市、衢州市、舟山市、台州市、丽水市"),
    ("安徽省", "合肥市、芜湖市、蚌埠市、淮南市、马鞍山市、淮北市、铜陵市、安庆市、黄山市、滁州市、阜阳市、宿州市、六安市、亳州市、池州市、宣城市"),
    ("福建省", "福州市、厦门市、莆田市、三明市、泉州市、漳州市、南平市、龙岩市、宁德市"),
    ("江西省", "南昌市、景德镇市、萍乡市、九江市、新余市、鹰潭市、赣州市、吉安市、宜春市、抚州市、上饶市"),
    ("山东省", "济南市、青岛市、淄博市、枣庄市、东营市、烟台市、潍坊市、济宁市、泰安市、威海市、日照市、临沂市、德州市、聊城市、滨州市、菏泽市"),
    ("河南省", "郑州市、开封市、洛阳市、平顶山市、安阳市、鹤壁市、新乡市、焦作市、濮阳市、许昌市、漯河市、三门峡市、南阳市、商丘市、信阳市、周口市、驻马店市"),
    ("湖北省", "武汉市、黄石市、十堰市、宜昌市、襄阳市、鄂州市、荆门市、孝感市、荆州市、黄冈市、咸宁市、随州市、恩施土家族苗族自治州"),
    ("湖南省", "长沙市、株洲市、湘潭市、衡阳市、邵阳市、岳阳市、常德市、张家界市、益阳市、郴州市、永州市、怀化市、娄底市、湘西土家族苗族自治州"),
    ("广东省", "广州市、韶关市、深圳市、珠海市、汕头市、佛山市、江门市、湛江市、茂名市、肇庆市、惠州市、梅州市、汕尾市、河源市、阳江市、清远市、东莞市、中山市、潮州市、揭阳市、云浮市"),
    ("广西壮族自治区", "南宁市、柳州市、桂林市、梧州市、北海市、防城港市、钦州市、贵港市、玉林市、百色市、贺州市、河池市、来宾市、崇左市"),
    ("海南省", "海口市、三亚市、三沙市、儋州市"),
    ("四川省", "成都市、自贡市、攀枝花市、泸州市、德阳市、绵阳市、广元市、遂宁市、内江市、乐山市、南充市、眉山市、宜宾市、广安市、达州市、雅安市、巴中市、资阳市、阿坝藏族羌族自治州、甘孜藏族自治州、凉山彝族自治州"),
    ("贵州省", "贵阳市、六盘水市、遵义市、安顺市、毕节市、铜仁市、黔西南布依族苗族自治州、黔东南苗族侗族自治州、黔南布依族苗族自治州"),
    ("云南省", "昆明市、曲靖市、玉溪市、保山市、昭通市、丽江市、普洱市、临沧市、楚雄彝族自治州、红河哈尼族彝族自治州、文山壮族苗族自治州、西双版纳傣族自治州、大理白族自治州、德宏傣族景颇族自治州、怒江傈僳族自治州、迪庆藏族自治州"),
    ("西藏自治区", "拉萨市、日喀则市、昌都市、林芝市、山南市、那曲市、阿里地区"),
    ("陕西省", "西安市、铜川市、宝鸡市、咸阳市、渭南市、延安市、汉中市、榆林市、安康市、商洛市"),
    ("甘肃省", "兰州市、嘉峪关市、金昌市、白银市、天水市、武威市、张掖市、平凉市、酒泉市、庆阳市、定西市、陇南市、临夏回族自治州、甘南藏族自治州"),
    ("青海省", "西宁市、海东市、海北藏族自治州、黄南藏族自治州、海南藏族自治州、果洛藏族自治州、玉树藏族自治州、海西蒙古族藏族自治州"),
    ("宁夏回族自治区", "银川市、石嘴山市、吴忠市、固原市、中卫市"),
    ("新疆维吾尔自治区", "乌鲁木齐市、克拉玛依市、吐鲁番市、哈密市、昌吉回族自治州、博尔塔拉蒙古自治州、巴音郭楞蒙古自治州、阿克苏地区、克孜勒苏柯尔克孜自治州、喀什地区、和田地区、伊犁哈萨克自治州、塔城地区、阿勒泰地区"),
)

_REGIONS: Final[tuple[tuple[str, tuple[str, ...]], ...]] = tuple(
    (province, tuple(dict.fromkeys(city_text.split("、"))))
    for province, city_text in _REGION_TEXT
)
_CITY_MAP: Final[dict[str, frozenset[str]]] = {
    province: frozenset(cities) for province, cities in _REGIONS
}


class SourceLocationInvalidError(ValueError):
    pass


def optional_name(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def region_catalog() -> list[dict[str, object]]:
    return [
        {"name": province, "cities": list(cities)}
        for province, cities in _REGIONS
    ]


def validate_source_location(
    source_type: str,
    province_name: str | None,
    city_name: str | None,
) -> tuple[str | None, str | None]:
    province = optional_name(province_name)
    city = optional_name(city_name)

    if source_type == "UNKNOWN":
        if province is not None or city is not None:
            raise SourceLocationInvalidError("来源不详不能填写来源省市")
        return None, None

    if source_type == "LOCAL_HUAINAN":
        if province not in (None, "安徽省") or city not in (None, "淮南市"):
            raise SourceLocationInvalidError("市内串码只能是安徽省淮南市")
        return "安徽省", "淮南市"

    if source_type == "ANHUI_OTHER_CITY":
        if province not in (None, "安徽省"):
            raise SourceLocationInvalidError("省内市外的来源省必须是安徽省")
        if city is None or city == "淮南市" or city not in _CITY_MAP["安徽省"]:
            raise SourceLocationInvalidError("请选择淮南市以外的安徽省城市")
        return "安徽省", city

    if source_type == "OUTSIDE_PROVINCE":
        if province is None:
            raise SourceLocationInvalidError("外省流入必须选择来源省")
        if province == "安徽省":
            raise SourceLocationInvalidError("外省流入不能选择安徽省")
        if province not in _CITY_MAP:
            raise SourceLocationInvalidError("来源省不在可选地区范围内")
        if city is None:
            return province, "不详"
        if city != "不详" and city not in _CITY_MAP[province]:
            raise SourceLocationInvalidError("来源市不属于所选来源省")
        return province, city

    raise SourceLocationInvalidError("卷烟来源地类型无效")


def source_key(
    source_type: str,
    province_name: str | None,
    city_name: str | None,
) -> str:
    province, city = validate_source_location(source_type, province_name, city_name)
    return f"{source_type}|{province or ''}|{city or ''}"
