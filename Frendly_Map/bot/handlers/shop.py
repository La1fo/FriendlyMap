from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes


async def shop_stub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer("Магазин пока закрыт", show_alert=True)


shop_stub_handler = CallbackQueryHandler(shop_stub, pattern="^shop_stub$")
