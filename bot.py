import os
import asyncio
import tempfile
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from picarta import Picarta
from dotenv import load_dotenv

# Конфигурационные параметры
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") 
PICARTA_API_TOKEN = os.getenv("PICARTA_API_TOKEN") 

#if not all([TELEGRAM_TOKEN, PICARTA_API_TOKEN]):
#    raise EnvironmentError("Missing required environment variables")

# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()


async def download_photo(message: types.Message, bot: Bot) -> str:
    """Скачивает фото и возвращает путь к временному файлу"""
    photo = message.photo[-1]  # Берем самое высокое качество
    file = await bot.get_file(photo.file_id)
    
    # Создаем временный файл
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    temp_path = temp_file.name
    await bot.download_file(file.file_path, temp_path)
    
    return temp_path


def format_result(result: dict) -> str:
    """Форматирует результат Picarta в читаемый текст"""
    if not result.get('predictions'):
        return "Не удалось определить местоположение на изображении."
    
    response = ["📍 Результаты геолокации:"]
    for idx, pred in enumerate(result['predictions'], 1):
        response.append(
            f"{idx}. Широта: {pred['latitude']:.4f}, "
            f"Долгота: {pred['longitude']:.4f}\n"
            f"   Уверенность: {pred['score']:.2%}"
        )
    
    return "\n".join(response)


@dp.message(Command("start"))
async def start_command(message: types.Message):
    """Обработчик команды /start"""
    await message.answer(
        "Привет! Отправьте мне фотографию для определения геолокации.(бесплатно 3 раза максимум)\n"
        "Используется сервис Picarta.ai"
    )


@dp.message(lambda message: message.photo)
async def handle_photo(message: types.Message):
    """Обработчик фотографий"""
    try:
        # Скачиваем фото
        temp_path = await download_photo(message, bot)
        
        # Инициализируем Picarta
        localizer = Picarta(PICARTA_API_TOKEN)
        
        # Отправляем запрос в Picarta (асинхронно)
        result = await asyncio.to_thread(
            localizer.localize,
            img_path=temp_path
        )
        
        # Форматируем и отправляем результат
        response_text = format_result(result)
        await message.answer(response_text)
        
    except Exception as e:
        await message.answer(f"🚫 Ошибка: {str(e)}")
    finally:
        # Удаляем временный файл
        if 'temp_path' in locals():
            os.unlink(temp_path)


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())