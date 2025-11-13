"""
Простой тест для проверки SSE upload endpoint
"""
import asyncio
import io
from fastapi.testclient import TestClient
from src.app import get_application


async def test_sse_upload_basic():
    """Базовый тест SSE upload endpoint."""
    
    app = get_application()
    client = TestClient(app)
    
    # Создаем тестовый файл
    test_file_content = b"fake video content"
    test_file = ("test.mp4", io.BytesIO(test_file_content), "video/mp4")
    
    print("Testing SSE upload endpoint...")
    
    try:
        # Отправляем POST запрос на SSE endpoint
        with client.stream("POST", "/files/upload/stream", files={"file": test_file}) as response:
            print(f"Response status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type')}")
            
            # Читаем первые несколько SSE событий
            events_count = 0
            for line in response.iter_lines():
                if line:
                    print(f"SSE Line: {line}")
                    events_count += 1
                    if events_count >= 10:  # Ограничиваем количество для теста
                        break
            
            print(f"Received {events_count} SSE events")
            
    except Exception as e:
        print(f"Error during test: {e}")


if __name__ == "__main__":
    asyncio.run(test_sse_upload_basic())