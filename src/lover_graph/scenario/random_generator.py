"""Random matchmaking scenario generator."""

from __future__ import annotations

import random
import uuid
from datetime import datetime

from lover_graph.schemas.behavior_constraints import SimulationDefaults
from lover_graph.schemas.role_persona import DEFAULT_PERSONAS, BigFivePersona, RolePersona
from lover_graph.schemas.trial_constraints import SessionConstraints
from lover_graph.schemas.trial_scenario import (
    FiveWOneH,
    MatchScenario,
    NarrativeScene,
    PartySide,
    SimulationConfig,
    TraitItem,
    TraitPool,
    TraitStatus,
    TraitVisibility,
    ValueTension,
)

_MEETING_TEMPLATES = [
    {
        "meeting_type": "都市白领相亲局",
        "what": "同城白领经媒婆介绍初次见面",
        "venue_tpl": "{city}某茶餐厅包厢",
        "tensions": ["要不要尽快结婚", "谁承担更多家务", "是否接受异地", "消费观是否一致"],
        "male_ideal_tpl": "希望找{age_pref}岁左右、{trait_pref}、能{life_pref}的对象",
        "female_ideal_tpl": "希望男方{job_pref}、{asset_pref}、{personality_pref}",
    },
    {
        "meeting_type": "县城熟人介绍局",
        "what": "父母托媒婆在县城饭店组局相亲",
        "venue_tpl": "{city}老字号饭店二楼",
        "tensions": ["要不要跟父母同住", "彩礼五金怎么谈", "房子写谁名字", "要不要马上定亲"],
        "male_ideal_tpl": "想找个{trait_pref}、{age_pref}岁上下、{life_pref}的媳妇",
        "female_ideal_tpl": "希望男方{asset_pref}、人{personality_pref}、{job_pref}",
    },
    {
        "meeting_type": "高知家庭相亲局",
        "what": "双方家长经媒婆撮合，年轻人初次正式见面",
        "venue_tpl": "{city}某书店咖啡角",
        "tensions": ["事业与家庭如何平衡", "是否要孩子", "是否接受对方过往感情", "价值观是否合拍"],
        "male_ideal_tpl": "理想对象是{trait_pref}、{personality_pref}、能{life_pref}",
        "female_ideal_tpl": "希望对方{job_pref}、{personality_pref}、{asset_pref}",
    },
]

_TRAIT_CATALOG = [
    ("颜值", "外貌", "第一眼印象与穿搭气质"),
    ("年龄", "基本信息", "实际年龄与对外说法是否一致"),
    ("书生气", "气质", "谈吐斯文程度、学历背景"),
    ("工作", "职业", "单位、收入区间、稳定性"),
    ("房子", "资产", "有无婚房、位置、是否全款"),
    ("车子", "资产", "车型、是否本人名下"),
    ("家庭背景", "家世", "父母职业、兄弟姐妹情况"),
    ("隐疾", "健康", "是否有不宜公开的健康或心理状况"),
    ("富二代", "家世", "家庭经济实力与消费方式"),
    ("恋爱观", "观念", "对婚姻节奏、忠诚、独立的看法"),
]

_SURNAMES = "张王李赵刘陈杨黄周吴"
_MALE_GIVEN = "伟强磊洋勇军杰涛明超刚平"
_FEMALE_GIVEN = "芳娜敏静丽艳娟秀英华桂兰"
_CITIES = ["杭州", "南京", "深圳", "成都", "武汉", "郑州", "长沙"]


def _rand_gender(rng: random.Random) -> str:
    return rng.choice(["male", "female"])


def _rand_name(rng: random.Random, gender: str | None = None) -> tuple[str, str]:
    gender = gender or _rand_gender(rng)
    given_pool = _MALE_GIVEN if gender == "male" else _FEMALE_GIVEN
    name = rng.choice(_SURNAMES) + rng.choice(given_pool)
    if rng.random() > 0.5:
        name += rng.choice(given_pool)
    return name, gender


def _vary_persona(base: RolePersona, rng: random.Random) -> RolePersona:
    bf = base.big_five

    def jitter(v: float) -> float:
        return max(0.0, min(1.0, v + rng.uniform(-0.15, 0.15)))

    return base.model_copy(
        update={
            "big_five": BigFivePersona(
                openness=jitter(bf.openness),
                conscientiousness=jitter(bf.conscientiousness),
                extraversion=jitter(bf.extraversion),
                agreeableness=jitter(bf.agreeableness),
                neuroticism=jitter(bf.neuroticism),
            )
        }
    )


def _pick_trait_text(rng: random.Random, trait_name: str, side: str) -> str:
    samples = {
        "颜值": ["清秀耐看", "五官端正", "打扮时尚", "朴素邻家"],
        "年龄": ["28岁", "30岁", "32岁", "26岁"],
        "书生气": ["硕士毕业，说话慢条斯理", "本科，爱看书", "理工科，不太会说话", "文科，谈吐文雅"],
        "工作": ["互联网产品经理", "体制内科员", "私企销售", "中学老师", "自由职业设计师"],
        "房子": ["市区有一套两居室", "老家有房，城里还在攒首付", "父母名下一套老房", "暂无，计划婚后买"],
        "车子": ["有一辆代步车", "暂无车", "开家里旧车", "刚贷款买了新车"],
        "家庭背景": ["普通工薪家庭", "做小生意的家庭", "单亲家庭长大", "父母都是退休教师"],
        "隐疾": ["曾有轻度抑郁史，已恢复", "有轻微过敏，不影响生活", "腰伤旧疾，不能干重活", "暂无"],
        "富二代": ["家里做建材，条件尚可", "普通人家，非富二代", "父母开厂，出手大方", "自称普通，实际家境不错"],
        "恋爱观": ["认定了就要结婚", "先谈恋爱再看", "慢热型，讨厌被催", "重视精神契合"],
    }
    opts = samples.get(trait_name, ["情况一般"])
    return rng.choice(opts)


def _parents_private_knowledge(rng: random.Random, side: str) -> str:
    memories = [
        "年轻时因为彩礼谈崩过一段姻缘，至今心有余悸。",
        "曾目睹邻居闪婚后迅速离婚，对草率定亲非常警惕。",
        "自己当年瞒着家里谈恋爱，深知信息差会埋雷。",
        "上一辈因为婆媳同住闹得很僵，对婚后居住问题格外敏感。",
        "见过有人隐瞒身体旧疾导致婚后矛盾，因此主张关键条件必须问清。",
    ]
    return f"【仅{side}家长可见】刻骨铭心的经历：{rng.choice(memories)}"


def generate_random_scenario(
    defaults: SimulationDefaults | None = None,
    seed: int | None = None,
) -> MatchScenario:
    defaults = defaults or SimulationDefaults()
    rng = random.Random(seed if seed is not None else defaults.random_seed)

    tpl = rng.choice(_MEETING_TEMPLATES)
    male_name, male_gender = _rand_name(rng, "male")
    female_name, female_gender = _rand_name(rng, "female")
    city = rng.choice(_CITIES)
    session_id = f"LOVE-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"

    male_parents_name, _ = _rand_name(rng, "male")
    female_parents_name, _ = _rand_name(rng, "female")
    matchmaker_name = "王媒婆"
    assistant_name = "小李"

    n_traits = rng.randint(8, 12)
    mb = rng.randint(2, 4)
    fb = rng.randint(2, 4)
    while mb + fb > n_traits:
        fb = max(2, fb - 1)

    mb_ids = [f"T{i:02d}" for i in range(1, mb + 1)]
    fb_ids = [f"T{i:02d}" for i in range(mb + 1, mb + fb + 1)]
    chosen = rng.sample(_TRAIT_CATALOG, min(n_traits, len(_TRAIT_CATALOG)))
    while len(chosen) < n_traits:
        chosen.append(rng.choice(_TRAIT_CATALOG))

    items: list[TraitItem] = []
    for i, (tname, ttype, tdesc) in enumerate(chosen[:n_traits], start=1):
        tid = f"T{i:02d}"
        is_mb = tid in mb_ids
        is_fb = tid in fb_ids
        submitted = PartySide.MALE if is_mb else (PartySide.FEMALE if is_fb else None)
        is_hidden = tname in ("隐疾", "富二代", "房子") and rng.random() > 0.4
        status = TraitStatus.SUBMITTED if submitted else (
            TraitStatus.WITHHELD if is_hidden else TraitStatus.RUMORED
        )
        side = "男方" if is_mb else ("女方" if is_fb else "媒婆掌握")
        items.append(
            TraitItem(
                id=tid,
                name=tname,
                type=ttype,
                description=f"{side}相关：{_pick_trait_text(rng, tname, side)}",
                proves=tdesc,
                holder=submitted or PartySide.UNKNOWN,
                submitted_by=submitted,
                status=status,
                known_to=TraitVisibility(
                    male=is_mb or is_fb or tname in ("颜值", "年龄", "书生气") or rng.random() > 0.6,
                    female=is_mb or is_fb or tname in ("颜值", "年龄", "书生气") or rng.random() > 0.6,
                    venue=is_mb or is_fb or tname not in ("隐疾",),
                ),
                content_access=TraitVisibility(
                    male=is_mb or (is_fb and tname in ("颜值", "年龄", "工作")),
                    female=is_fb or (is_mb and tname in ("颜值", "年龄", "工作")),
                    venue=is_mb or is_fb,
                ),
            )
        )

    age_pref = rng.choice(["26到28", "28到30", "30左右"])
    trait_pref = rng.choice(["温柔顾家", "独立有主见", "开朗爱笑", "文静内敛"])
    life_pref = rng.choice(["一起打拼", "稳定过日子", "互相尊重各自空间"])
    job_pref = rng.choice(["工作稳定", "有上进心", "收入靠谱", "不要太忙"])
    asset_pref = rng.choice(["有房或有清晰计划", "人品第一条件第二", "家里底子清楚"])
    personality_pref = rng.choice(["踏实", "会疼人", "不油嘴滑舌", "有责任感"])

    fmt = dict(
        age_pref=age_pref,
        trait_pref=trait_pref,
        life_pref=life_pref,
        job_pref=job_pref,
        asset_pref=asset_pref,
        personality_pref=personality_pref,
    )
    male_ideal = tpl["male_ideal_tpl"].format(**fmt)
    female_ideal = tpl["female_ideal_tpl"].format(**fmt)

    male_persona = _vary_persona(DEFAULT_PERSONAS["male"], rng)
    female_persona = _vary_persona(DEFAULT_PERSONAS["female"], rng)
    male_parents_persona = _vary_persona(DEFAULT_PERSONAS["male_parents"], rng)
    female_parents_persona = _vary_persona(DEFAULT_PERSONAS["female_parents"], rng)

    has_mp = defaults.male_has_lawyer
    has_fp = defaults.female_has_lawyer

    sim = SimulationConfig(
        max_rounds=defaults.max_rounds,
        male_has_lawyer=has_mp,
        female_has_lawyer=has_fp,
        seed=seed,
    )
    sim.constraints = SessionConstraints(**defaults.to_trial_constraints_kwargs())
    sim.behavior = defaults.behavior

    return MatchScenario(
        scenario_id=session_id,
        source="随机生成（loverGraph scenario/random_generator）",
        five_w_one_h=FiveWOneH(
            who=f"媒婆{matchmaker_name}组局；男方{male_name}（家长{male_parents_name}）；女方{female_name}（家长{female_parents_name}）",
            what=tpl["what"],
            when=f"{datetime.now().year}年{rng.randint(1,12)}月经媒婆撮合初次见面",
            where=tpl["venue_tpl"].format(city=city),
            why="双方到了适婚年龄，家长希望正式见一面，年轻人也愿给个机会",
            how="媒婆定包厢、订流程，双方家长陪同，男女主初次正式相亲",
        ),
        narrative=NarrativeScene(
            title=f"一场{tpl['meeting_type']}",
            synopsis=(
                f"{city}{tpl['meeting_type']}：{male_name} 与 {female_name} 在媒婆安排下初次见面。"
                f"桌上既有年轻人，也有家长。条件、期待、信息差交织，"
                f"最终可能谈成，也可能礼貌收场。{defaults.budget_synopsis()}"
            ),
            atmosphere="包厢里茶香与客套话并存，媒婆面无表情地控场",
        ),
        venue=tpl["venue_tpl"].format(city=city),
        meeting_type=tpl["meeting_type"],
        parties={
            "matchmaker": {
                "name": matchmaker_name,
                "gender": "female",
                "persona": DEFAULT_PERSONAS["matchmaker"].model_dump(),
            },
            "clerk": {"name": assistant_name},
            "male": {
                "name": male_name,
                "gender": male_gender,
                "has_lawyer": has_mp,
                "lawyer_name": male_parents_name,
                "lawyer_gender": "male",
                "profile": f"本人{male_name}，{male_persona.speech_style}。",
                "ideal_partner": male_ideal,
                "private_knowledge": "对相亲有点紧张，很多条件还没想好怎么开口。",
                "persona": male_persona.model_dump(),
            },
            "male_parents": {
                "name": male_parents_name,
                "gender": "male",
                "profile": f"{male_name}的父亲/家长代表，替儿子把把关。",
                "ideal_partner": f"希望儿媳{trait_pref}、{asset_pref}，别让我儿子吃亏。",
                "private_knowledge": _parents_private_knowledge(rng, "男方"),
                "persona": male_parents_persona.model_dump(),
            },
            "female": {
                "name": female_name,
                "gender": female_gender,
                "has_lawyer": has_fp,
                "lawyer_name": female_parents_name,
                "lawyer_gender": "female",
                "profile": f"本人{female_name}，{female_persona.speech_style}。",
                "ideal_partner": female_ideal,
                "private_knowledge": "有些底线不会第一次见面就全说。",
                "persona": female_persona.model_dump(),
            },
            "female_parents": {
                "name": female_parents_name,
                "gender": "female",
                "profile": f"{female_name}的母亲/家长代表，替女儿掌眼。",
                "ideal_partner": f"希望女婿{job_pref}、{personality_pref}，别委屈了我女儿。",
                "private_knowledge": _parents_private_knowledge(rng, "女方"),
                "persona": female_parents_persona.model_dump(),
            },
        },
        ideal_partner_notes=f"男方期待：{male_ideal}；女方期待：{female_ideal}",
        tension_points=tpl["tensions"],
        value_tensions=[
            ValueTension(
                axis="稳定 vs 自由",
                male_values=["Security: family", "Face"],
                female_values=["Autonomy", "Fairness"],
                description="一方更看重稳定成家，另一方更在意个人空间与尊重。",
            )
        ],
        relationship_issues=["条件是否说全", "家长介入尺度", "节奏是否合适", "媒婆合约边界"],
        trait_pool=TraitPool(
            total_count=n_traits,
            description=f"共{n_traits}项条件/信息；男方主动展示{mb}项，女方主动展示{fb}项",
            items=items,
            male_bundle=mb_ids,
            female_bundle=fb_ids,
        ),
        simulation=sim,
    )
