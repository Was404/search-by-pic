import os
import asyncio
import tempfile
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from picarta import Picarta
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Конфигурация логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Проверка токенов
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
PICARTA_API_TOKEN = os.getenv("PICARTA_API_TOKEN")

if not all([TELEGRAM_TOKEN, PICARTA_API_TOKEN]):
    logger.error("Отсутствуют необходимые переменные окружения!")
    raise EnvironmentError("Необходимые переменные окружения не найдены")

# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()


async def download_photo(message: types.Message) -> str:
    """Скачивание фото с сохранением в временный файл"""
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        temp_path = temp_file.name
        
        logger.info(f"Скачивание фото от {message.from_user.id} [Размер: {photo.file_size} bytes]")
        await bot.download_file(file.file_path, temp_path)
        
        return temp_path
    except Exception as e:
        logger.error(f"Ошибка при скачивании фото: {str(e)}")
        raise


def format_result(result: dict) -> str:
    """Форматирование результата Picarta"""
    if not result.get('predictions'):
        logger.warning("Нет предсказаний в ответе Picarta")
        return "Не удалось определить местоположение на изображении."
    
    logger.info(f"Успешно получено {len(result['predictions'])} предсказаний")
    return "\n".join([
        f"{idx}. Широта: {pred['latitude']:.4f}, Долгота: {pred['longitude']:.4f}\n"
        f"   Уверенность: {pred['score']:.2%}"
        for idx, pred in enumerate(result['predictions'], 1)
    ])


@dp.message(Command("start"))
async def start_command(message: types.Message):
    """Обработчик команды /start"""
    logger.info(f"Новый пользователь: {message.from_user.id}")
    await message.answer(
        "Привет! Отправьте мне фотографию для определения геолокации.\n"
        "Используется сервис Picarta.ai"
    )


@dp.message(lambda message: message.photo)
async def handle_photo(message: types.Message):
    """Обработчик фотографий"""
    user_id = message.from_user.id
    logger.info(f"Обработка фото от пользователя {user_id}")
    
    temp_path = None
    try:
        temp_path = await download_photo(message)
        
        logger.debug(f"Запуск обработки Picarta для файла: {temp_path}")
        localizer = Picarta(PICARTA_API_TOKEN)
        
        # Замер времени выполнения
        start_time = datetime.now()
        result = await asyncio.to_thread(localizer.localize, img_path=temp_path)
        processing_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"Picarta обработала фото за {processing_time:.2f} сек")
        
        response_text = format_result(result)
        await message.answer(response_text)
        
    except Exception as e:
        error_msg = f"Ошибка обработки для пользователя {user_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await message.answer("🚫 Произошла ошибка при обработке изображения")
        
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
                logger.debug(f"Временный файл {temp_path} удален")
            except Exception as e:
                logger.error(f"Ошибка удаления файла: {str(e)}")


async def on_startup():
    """Действия при запуске бота"""
    logger.info("Бот успешно запущен!")
    await bot.send_message(chat_id=os.getenv("ADMIN_CHAT_ID"), text="🟢 Бот запущен")


async def on_shutdown():
    """Действия при остановке бота"""
    logger.warning("Остановка бота!")
    await bot.send_message(chat_id=os.getenv("ADMIN_CHAT_ID"), text="🔴 Бот остановлен")
    await bot.session.close()


async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"Критическая ошибка: {str(e)}", exc_info=True)
    finally:
        await on_shutdown()

if __name__ == "__main__":
    asyncio.run(main())