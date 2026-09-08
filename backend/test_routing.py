# 测试 ConversationMessage TypedDict 的 .get() 方法
import sys
sys.path.insert(0, '.')

from agent.types import ConversationMessage
from datetime import datetime

msg = ConversationMessage(role="assistant", content="已收到您的选择。请问选择哪个策略？", timestamp=datetime.now().isoformat())

print(f"type(msg) = {type(msg)}")
print(f"msg.get('content') = {msg.get('content')}")
print(f"msg['content'] = {msg['content']}")
print(f"'role' in msg = {'role' in msg}")
print(f"msg.items() = {list(msg.items())}")
