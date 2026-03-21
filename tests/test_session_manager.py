"""会话管理模块单元测试"""

import pytest
from unittest.mock import patch, MagicMock
from hybrid_agent.core.session_manager import (
    SessionManager,
    get_session_manager,
)
from hybrid_agent.core.config import (
    MAX_ROUNDS_BEFORE_SUMMARY,
    SESSION_TTL,
    SESSION_MAX_SIZE,
)


class TestSessionManager:
    """会话管理器测试"""

    def test_get_or_create_new_session(self):
        """测试创建新会话"""
        manager = SessionManager()
        session = manager.get_or_create("test_thread_1")
        
        assert session["thread_id"] == "test_thread_1"
        assert session["message_count"] == 0
        assert session["summary"] == ""

    def test_get_or_create_existing_session(self):
        """测试获取已有会话"""
        manager = SessionManager()
        
        session1 = manager.get_or_create("test_thread_2")
        session1["message_count"] = 5
        
        session2 = manager.get_or_create("test_thread_2")
        assert session2["message_count"] == 5

    def test_increment_message_count(self):
        """测试消息计数增加"""
        manager = SessionManager()
        
        count = manager.increment_message_count("test_thread_3")
        assert count == 1
        
        count = manager.increment_message_count("test_thread_3")
        assert count == 2

    def test_should_compress_threshold(self):
        """测试压缩阈值判断"""
        manager = SessionManager()
        thread_id = "test_thread_4"
        
        # 初始不需要压缩
        assert not manager.should_compress(thread_id)
        
        # 达到阈值时需要压缩
        for _ in range(MAX_ROUNDS_BEFORE_SUMMARY):
            manager.increment_message_count(thread_id)
        
        assert manager.should_compress(thread_id)

    def test_update_summary(self):
        """测试更新摘要"""
        manager = SessionManager()
        thread_id = "test_thread_5"
        
        manager.update_summary(thread_id, "这是摘要内容", 10)
        
        summary = manager.get_summary(thread_id)
        assert summary == "这是摘要内容"

    def test_delete_session(self):
        """测试删除会话"""
        manager = SessionManager()
        thread_id = "test_thread_6"
        
        manager.get_or_create(thread_id)
        manager.delete_session(thread_id)
        
        # 删除后再获取应该是新会话
        session = manager.get_or_create(thread_id)
        assert session["message_count"] == 0
        assert session["summary"] == ""

    def test_compress_session_empty_messages(self):
        """测试空消息列表压缩"""
        manager = SessionManager()
        thread_id = "test_thread_7"
        
        result = manager.compress_session(thread_id, [])
        assert result == ""

    def test_compress_session_with_messages(self):
        """测试有消息时压缩"""
        manager = SessionManager()
        thread_id = "test_thread_8"
        
        messages = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好，有什么可以帮助你的？"},
        ]
        
        with patch.object(
            manager,
            '_generate_summary',
            return_value="用户问候，助手回应"
        ):
            result = manager.compress_session(thread_id, messages)
            assert result == "用户问候，助手回应"


class TestSessionManagerSingleton:
    """单例模式测试"""

    def test_singleton(self):
        """测试全局单例"""
        manager1 = get_session_manager()
        manager2 = get_session_manager()
        assert manager1 is manager2

    def test_singleton_state_persistence(self):
        """测试单例状态持久化"""
        manager = get_session_manager()
        thread_id = "singleton_test_thread"
        
        manager.increment_message_count(thread_id)
        count = manager.get_or_create(thread_id)["message_count"]
        assert count == 1


class TestSessionManagerConfig:
    """配置测试"""

    def test_ttl_config(self):
        """测试 TTL 配置"""
        assert SESSION_TTL == 7200  # 2 小时

    def test_max_size_config(self):
        """测试最大会话数配置"""
        assert SESSION_MAX_SIZE == 1000

    def test_max_rounds_config(self):
        """测试压缩阈值配置"""
        assert MAX_ROUNDS_BEFORE_SUMMARY == 20
