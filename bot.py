import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

import database
import wallets
import llm

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# In-memory session context for conversation history (User ID -> List of Dict messages)
# For production, this should be bounded and periodically cleared, or saved to a DB.
chat_sessions = {}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Answers any message using the LLM and the user's wallet context."""
    user = update.effective_user
    user_text = update.message.text
    
    # Initialize DB user if not exists
    db_user = database.get_user(user.id)
    if not db_user:
        await update.message.reply_text("Welcome! Generating your Ethereum and Solana wallets. Please wait a moment...")
        eth_wallet = wallets.generate_eth_wallet()
        sol_wallet = wallets.generate_sol_wallet()
        
        database.create_user(
            user_id=user.id,
            username=user.username or "",
            eth_data=eth_wallet,
            sol_data=sol_wallet
        )
        db_user = database.get_user(user.id)

    # Initialize chat history for the user
    if user.id not in chat_sessions:
        system_prompt = f"""
        You are Anna, an AI prediction market and trading assistant. 
        Your user is {user.first_name}. 
        Here is the user's wallet information:
        - Ethereum Address: {db_user['eth_address']}
        - Solana Address: {db_user['sol_address']}
        
        You can help the user check their wallet balances, browse Kalshi prediction markets, make mock trades, or just chat. 
        If the user asks for their balance without specifying a chain, default to fetching ONLY the Solana balance using your tools. You can fetch the Ethereum balance if explicitly requested. 
        If the user asks to "suggest me some markets" or asks about prediction markets, USE YOUR AVAILABLE TOOLS to fetch active markets from Kalshi. When you return the markets, ALWAYS start your response with the phrase "Here are some active markets:" and list them nicely.
        
        CRITICAL TRADING RULES:
        1. NEVER execute a trade immediately when the user requests it. 
        2. First, ask the user for explicit confirmation (e.g. "Do you want to confirm this trade of X on Y?").
        3. ONLY use the execute_trade tool AFTER the user explicitly replies "yes" or "confirm" to your prompt.
        4. When you call execute_trade, pass the user's Solana Address listed above.
        """
        chat_sessions[user.id] = [{"role": "system", "content": system_prompt}]
        
    # Append the user's new message
    chat_sessions[user.id].append({"role": "user", "content": user_text})

    # Show a typing indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    # Get response from LLM
    assistant_reply = await llm.get_chat_response(chat_sessions[user.id])
    
    # Append Assistant's reply to history
    chat_sessions[user.id].append({"role": "assistant", "content": assistant_reply})

    # Reply to the user
    await update.message.reply_text(assistant_reply, parse_mode="Markdown")


if __name__ == '__main__':
    if not BOT_TOKEN:
        print("BOT_TOKEN is missing in the environment.")
        exit(1)

    # Initialize DB
    database.init_db()

    # Build bot
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add single handler for ALL text messages (including commands which telegram treats as text starting with /)
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    print("Bot is running...")
    app.run_polling()

