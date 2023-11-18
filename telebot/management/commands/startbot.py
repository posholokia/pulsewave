from django.core.management.base import BaseCommand
import asyncio

from aiogram import Bot, Dispatcher
from telebot.config_data.config import Config, load_config
from telebot.handlers import other_handlers, user_handlers


# Название класса обязательно - "Command"
class Command(BaseCommand):
  	# Используется как описание команды обычно
    help = 'Just a command for launching a Telegram bot.'

    def handle(self, *args, **kwargs):
        async def main():
            # Загружаем конфиг в переменную config
            config: Config = load_config()

            # Инициализируем бот и диспетчер
            bot = Bot(token=config.tg_bot.token)
            dp = Dispatcher()

            # Регистриуем роутеры в диспетчере
            dp.include_router(user_handlers.router)
            dp.include_router(other_handlers.router)

            # Пропускаем накопившиеся апдейты и запускаем polling
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)

        asyncio.run(main())
