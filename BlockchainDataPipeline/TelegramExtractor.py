import os
from dotenv import load_dotenv, find_dotenv
import logging
import re
import requests
from pyrogram import Client, filters
from BlockchainDataPipeline.BlockchainDataHandler import (
    load_token_contract,
    fetch_token_data,
    fetch_liquidity_and_market_cap,
    fetch_holders,
    fetch_burned_tokens,
    fetch_top_holders,
    fetch_tax_info,
    fetch_liquidity_percentage,
    classify_airdrops
)


load_dotenv(find_dotenv())

def send_to_fastapi(data):
    try:
        response = requests.post(os.getenv('API_URL'), json=data)
        if response.status_code == 200:
            logging.info("Data sent to FastAPI successfully.")
            logging.info(f"FastAPI response: {response.json()}")
        else:
            logging.error(f"Failed to send data: {response.status_code} - {response.text}")
    except Exception as e:
        logging.exception(f"Error sending data to FastAPI: {e}")


# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("telegram_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TelegramBot")

# Telegram API details
app = Client("session", api_id=os.getenv('API_ID_ON_MESSAGE'), api_hash=os.getenv('API_HASH_ON_MESSAGE'))

# Function to extract data from a message
def extract_data(message):
    data = {}

    token_pair_match = re.search(r'\((\w+/\w+)\)', message)
    data['token_pair'] = token_pair_match.group(1) if token_pair_match else None

    liquidity_match = re.search(r'Initial Liquidity:\s+\$(\d+(,\d+)*)', message)
    data['initial_liquidity'] = liquidity_match.group(1).replace(',', '') if liquidity_match else None

    contract_match = re.search(r'Token contract:\s+(0x[a-fA-F0-9]{40})', message)
    data['contract_address'] = contract_match.group(1) if contract_match else None

    dextools_match = re.search(r'DEXTools:\s+(https?://[^\s]+)', message)
    data['dextools_url'] = dextools_match.group(1) if dextools_match else None

    return data

@app.on_message(filters.chat("DEXTNewPairsBotBSC"))
def parse_message(client, message):
    logger.info("New message received from Telegram channel.")
    try:
        raw_message = message.text
        logger.debug(f"Raw message: {raw_message}")

        extracted_data = extract_data(raw_message)
        logger.info(f"Extracted data: {extracted_data}")

        # Get the contract address
        contract_address = extracted_data.get('contract_address')

        if contract_address:
            logger.info(f"Contract Address: {contract_address}")

            # Load token contract
            token_contract = load_token_contract(contract_address)
            if token_contract:
                logger.info("Token contract loaded successfully.")

                # Fetch token data
                token_data = fetch_token_data(token_contract)
                if token_data:
                    logger.info(f"Token Data: {token_data}")

                # Fetch liquidity + market cap
                liquidity_data = None
                if token_data:
                    liquidity_data = fetch_liquidity_and_market_cap(contract_address, token_data)
                    if liquidity_data:
                        logger.info(f"Liquidity and Market Cap: {liquidity_data}")

                # Fetch holders
                holders = fetch_holders(contract_address)
                logger.info(f"Holders: {holders}")

                # Burned tokens
                burned_tokens = fetch_burned_tokens(contract_address)
                logger.info(f"Burned Tokens: {burned_tokens}")

                # Top holders
                top_holders = fetch_top_holders(contract_address)
                logger.info(f"Top Holders: {top_holders}")

                # Tax info
                tax_info = fetch_tax_info(contract_address)
                logger.info(f"Tax Information: {tax_info}")

                # Liquidity percentage
                liquidity_percentage = None
                if liquidity_data and "liquidity_base" in liquidity_data and "total_supply" in token_data:
                    liquidity_percentage = fetch_liquidity_percentage(
                        liquidity_data, 
                        token_data['total_supply']
                    )
                    logger.info(f"Liquidity Percentage: {liquidity_percentage}%")

                # Classify airdrops (requires transaction data — pseudo example)
                transactions = []  # If you have a method to fetch actual tx data, replace here
                airdrops = classify_airdrops(transactions)
                logger.info(f"Airdrops: {airdrops}")

                # ---------------------------
                # Combine data for FastAPI
                # ---------------------------
                # Keep dictionaries/lists as is so FastAPI can parse them properly
                result_data = {
                    "token_pair": extracted_data.get("token_pair"),  # already str or None
                    "initial_liquidity": extracted_data.get("initial_liquidity"),  # str or None
                    "contract_address": contract_address,  # str
                    "dextools_url": extracted_data.get("dextools_url"),  # str
                    "token_data": token_data if token_data else {},  # dict
                    "liquidity_data": liquidity_data if liquidity_data else {},  # dict
                    "holders": holders,  # int
                    "burned_tokens": burned_tokens,  # float
                    "top_holders": top_holders,  # list
                    "tax_info": tax_info if tax_info else {},  # dict
                    "liquidity_percentage": liquidity_percentage,  # float
                    "airdrops": airdrops,  # list
                }

                # Send data to FastAPI
                send_to_fastapi(result_data)

    except Exception as e:
        logger.error(f"Error while processing message: {e}", exc_info=True)

if __name__ == "__main__":
    logger.info("Starting Pyrogram client...")
    try:
        app.run()
    except Exception as e:
        logger.critical(f"Critical error: {e}", exc_info=True)
