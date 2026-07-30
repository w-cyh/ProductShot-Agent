from app.agents.creative_planner import CreativePlannerAgent
from app.agents.prompt_engineer import PromptEngineerAgent
from app.models import Project
from app.schemas import CreativePlanPayload, ProductAnalysisPayload


class VariantStyleProvider:
    name = "fake"
    model = "fake-planner"

    def __init__(self):
        self.system_prompt = ""

    def generate_json(self, **kwargs):
        self.system_prompt = kwargs["system_prompt"]
        return {
            "plans": [
                {
                    "plan_name": f"方向 {index}",
                    "applicable_platform": "小红书",
                    "visual_description": "简洁产品静物摄影",
                    "background_scene": "自然光桌面",
                    "visual_style": "高级极简风",
                    "main_selling_point": "材质",
                    "recommendation_reason": "适合受众",
                    "copywriting_direction": "克制",
                }
                for index in range(1, 4)
            ]
        }


def test_selected_style_is_canonicalized_without_rejecting_a_model_variant():
    provider = VariantStyleProvider()
    plans = CreativePlannerAgent(provider).run(
        Project(product_name="香薰蜡烛", target_platform="多平台"),
        ProductAnalysisPayload(
            product_type="香薰蜡烛",
            core_features=["手工"],
            target_audience_analysis="家居用户",
            recommended_selling_points=["质感"],
            recommended_visual_styles=["高级极简"],
            image_issues=[],
            marketing_angles=["礼赠"],
        ),
        style_presets=["高级极简"],
    )

    assert [plan.visual_style for plan in plans] == ["高级极简", "高级极简", "高级极简"]
    assert "do not add suffixes" in provider.system_prompt


def test_prompt_engineer_reserves_copy_space_without_generating_promotional_text():
    class CaptureProvider:
        name = "fake"
        model = "fake-prompt"

        def __init__(self):
            self.system_prompt = ""

        def generate_json(self, **kwargs):
            self.system_prompt = kwargs["system_prompt"]
            return {
                "positive_prompt": "product photo",
                "negative_prompt": "blur",
                "size": "1024x1024",
                "style": "minimal",
                "product_consistency_notes": "保留原始标签",
                "platform": "小红书",
                "generation_mode": "image_to_image",
            }

    provider = CaptureProvider()
    prompt = PromptEngineerAgent(provider).run(
        Project(product_name="香薰蜡烛", target_platform="多平台"),
        CreativePlanPayload(
            plan_name="方向",
            applicable_platform="小红书",
            visual_description="静物",
            background_scene="桌面",
            visual_style="高级极简",
            main_selling_point="材质",
            recommendation_reason="适合",
            copywriting_direction="克制",
        ),
    )

    assert "upper-right area" in provider.system_prompt
    assert "promotional copy" in provider.system_prompt
    assert "upper-right area" in prompt.positive_prompt
    assert "generated promotional text" in prompt.negative_prompt
