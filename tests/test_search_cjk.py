from __future__ import annotations

import json
from pathlib import Path

import pytest

from turritopsis.api import Turritopsis
from turritopsis.search import _terms, semantic_search


@pytest.fixture
def cjk_data_path(tmp_path: Path) -> Path:
    root = tmp_path / ".turritopsis"
    root.mkdir()
    path = root / "stages.json"
    path.write_text(json.dumps({
        "title": "长期项目", "subtitle": "共享事实", "version": 1,
        "currents": [
            {"id": "anatomy", "name": "现在有什么", "blurb": "当前组件与运行结构", "stages": [
                {"id": "anatomy.memory", "title": "记忆库架构", "body": """# 记忆库架构

Purpose: 描述记忆系统的当前结构
Search hints: 记忆库 存储 向量 检索
Summary: 记忆库跑在服务器上，用向量索引做检索
Verified: 2026-08-24
Status: verified
Authority: 记忆模块

## 知识

记忆库分三层：原始记录、压缩理解、认知提炼。
"""},
                {"id": "anatomy.scheduler", "title": "心跳调度器", "body": """# 心跳调度器

Purpose: 描述定时唤醒机制
Search hints: 心跳 调度 定时 唤醒
Summary: 心跳按固定间隔触发一次唤醒
Verified: 2026-08-24
Status: verified
Authority: 调度模块

## 知识

心跳间隔可以在运行时调整。
"""},
            ]},
            {"id": "manual", "name": "操作手册", "blurb": "怎么操作", "stages": [
                {"id": "manual.deploy", "title": "部署与生效", "body": """# 部署与生效

Search hints: 部署 上线 生效 重启
Summary: 改完代码需要重启服务才生效
Status: current
Authority: 部署流程

## 步骤

先编译，再重启，最后验收。
"""},
            ]},
        ],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_cjk_query_is_split_into_bigrams():
    # No spaces in Chinese, so whitespace tokenization alone yields one dead term.
    assert _terms("记忆库") == ["记忆", "忆库"]
    assert "记忆" in _terms("记忆库是怎么工作的")


def test_ascii_tokenization_is_unchanged():
    assert _terms("nginx config") == ["nginx", "config"]
    assert _terms("  MCP  Tools ") == ["mcp", "tools"]


def test_english_stop_words_do_not_outscore_configuration_terms():
    data = {
        "currents": [{
            "id": "project", "name": "Project", "blurb": "Shared project map",
            "stages": [
                {
                    "id": "project.orientation",
                    "title": "The project and where it is",
                    "body": "# The project and where it is\n\nSummary: The project as it is.\n",
                },
                {
                    "id": "surface.cli_contract",
                    "title": "CLI contract",
                    "body": (
                        "# CLI contract\n\n"
                        "Search hints: required configuration defaults defined\n"
                        "Summary: Command configuration and defaults.\n"
                    ),
                },
            ],
        }],
    }
    query = "required configuration and where defaults are defined"
    assert _terms(query) == ["required", "configuration", "defaults", "defined"]
    assert semantic_search(data, query)[0]["stage_id"] == "surface.cli_contract"


def test_mixed_script_query_keeps_ascii_terms_whole():
    assert _terms("nginx 配置") == ["nginx", "配置"]
    assert _terms("重启nginx") == ["重启", "nginx"]


def test_natural_language_chinese_question_finds_the_right_stage(cjk_data_path):
    api = Turritopsis(cjk_data_path)
    results = api.search_stages("记忆库是怎么工作的")["results"]
    assert results, "a natural-language Chinese question must not return zero results"
    assert results[0]["stage_id"] == "anatomy.memory"


def test_chinese_questions_route_across_currents(cjk_data_path):
    api = Turritopsis(cjk_data_path)
    assert api.search_stages("心跳怎么调")["results"][0]["stage_id"] == "anatomy.scheduler"
    assert api.search_stages("改完代码怎么生效")["results"][0]["stage_id"] == "manual.deploy"


def test_function_word_only_bigrams_are_dropped():
    # 怎么 / 的了 carry no signal and would match every stage.
    terms = _terms("记忆库是怎么样的")
    assert "怎么" not in terms
    assert "记忆" in terms
