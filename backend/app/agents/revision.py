"""Retired direct-prompt revision entry point.

Creative-direction revisions are now handled by ``CreativePlannerAgent`` and
image iterations create a fresh Prompt Pack only when the user starts a new
generation task.  This module remains as an explicit guard for local code that
may still import the old class; it is not exported by ``app.agents`` or exposed
by an API route.
"""


class RevisionAgent:
    def __init__(self, *_args, **_kwargs) -> None:
        raise RuntimeError("RevisionAgent 已移除；请改用创意方向修订或基于图片的迭代生成。")
