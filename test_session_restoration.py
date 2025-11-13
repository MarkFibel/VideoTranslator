"""
Тест для проверки восстановления состояния из сессии.
Использует httpx для тестирования эндпоинта /files/session/status
"""
import asyncio
import httpx

BASE_URL = "http://localhost:8000"


async def test_session_status():
    """Тестирует эндпоинт получения статуса сессии"""
    
    async with httpx.AsyncClient() as client:
        # Делаем запрос к эндпоинту статуса сессии
        response = await client.get(f"{BASE_URL}/files/session/status")
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        # Проверяем структуру ответа
        data = response.json()
        assert "pending" in data, "Отсутствует поле 'pending'"
        assert "need_download" in data, "Отсутствует поле 'need_download'"
        assert "file" in data, "Отсутствует поле 'file'"
        
        print("\n✅ Тест успешно пройден!")
        print(f"   - pending: {data['pending']}")
        print(f"   - need_download: {data['need_download']}")
        print(f"   - file: {data['file']}")


if __name__ == "__main__":
    print("🧪 Запуск теста эндпоинта /files/session/status\n")
    asyncio.run(test_session_status())
