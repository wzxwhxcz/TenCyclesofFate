import sys
import os
import random
from datetime import timedelta

# 将项目根目录添加到Python路径，以便能够导入 backend.app 中的模块
# 这使得脚本可以从项目根目录运行 (e.g., python scripts/generate_token.py)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.auth import create_access_token
from backend.app.config import settings

def generate_test_token():
    """
    生成一个用于测试的JWT令牌。
    """
    # 模拟一个来自Linux.do OAuth流程的用户信息
    # 您可以根据需要修改这些值

    id = random.randint(10000, 99999)
    test_user_payload = {
        "sub": "testuser-" + str(id),
        "id": id,
        "name": "Test User " + str(id),
        "trust_level": 4,
    }

    # 从配置中获取令牌过期时间
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # 创建令牌
    access_token = create_access_token(
        data=test_user_payload, expires_delta=expires_delta
    )

    print("--- Generated Test JWT Token ---")
    print(access_token)
    print("\n--- How to use ---")
    print("1. Copy the token above.")
    print("2. Open your browser's developer tools on the game page.")
    print("3. Go to the 'Application' (or 'Storage') tab.")
    print("4. Find the 'Cookies' section for this site.")
    print("5. Create a new cookie with:")
    print("   - Name: token")
    print(f"   - Value: [paste the token here]")
    print("6. Refresh the page. You should now be logged in as 'Test User'.")

if __name__ == "__main__":
    generate_test_token()