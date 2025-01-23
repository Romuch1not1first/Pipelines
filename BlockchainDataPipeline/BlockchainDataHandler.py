from web3 import Web3
import requests
import logging
import os
from dotenv import load_dotenv, find_dotenv


load_dotenv(find_dotenv())

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Binance Smart Chain node
BSC_RPC = "https://bsc-dataseed.binance.org/"
web3 = Web3(Web3.HTTPProvider(BSC_RPC))

# ERC20 ABI (simplified)
erc20_abi = [
    {
        "constant": True,
        "inputs": [],
        "name": "name",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
]


# Load the token contract
def load_token_contract(contract_address):
    try:
        token_contract_address = Web3.to_checksum_address(contract_address)
        return web3.eth.contract(address=token_contract_address, abi=erc20_abi)
    except Exception as e:
        print(f"Invalid contract address: {e}")
        return None

# Fetch token data
def fetch_token_data(token_contract):
    try:
        token_name = token_contract.functions.name().call()
        token_symbol = token_contract.functions.symbol().call()
        token_decimals = token_contract.functions.decimals().call()
        total_supply = token_contract.functions.totalSupply().call() / (10 ** token_decimals)

        return {
            "name": token_name,
            "symbol": token_symbol,
            "decimals": token_decimals,
            "total_supply": total_supply,
        }
    except Exception as e:
        print(f"Error fetching token data: {e}")
        return None

# Fetch Liquidity and Market Cap
def fetch_liquidity_and_market_cap(contract_address, token_data):
    try:
        contract_address = Web3.to_checksum_address(contract_address)  # Convert to checksum format
        pancake_factory_address = Web3.to_checksum_address("0xca143ce32fe78f1f7019d7d551a6402fc5350c73")
        pancake_factory_abi = [
            {
                "constant": True,
                "inputs": [
                    {"name": "_tokenA", "type": "address"},
                    {"name": "_tokenB", "type": "address"},
                ],
                "name": "getPair",
                "outputs": [{"name": "pair", "type": "address"}],
                "type": "function",
            }
        ]

        # Common base tokens
        base_tokens = {
            "WBNB": Web3.to_checksum_address("0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c"),
            "BUSD": Web3.to_checksum_address("0xe9e7cea3dedca5984780bafc599bd69add087d56"),
            "USDT": Web3.to_checksum_address("0x55d398326f99059ff775485246999027b3197955"),
        }

        factory_contract = web3.eth.contract(address=pancake_factory_address, abi=pancake_factory_abi)

        for base_name, base_address in base_tokens.items():
            pair_address = factory_contract.functions.getPair(contract_address, base_address).call()
            if pair_address != "0x0000000000000000000000000000000000000000":
                print(f"Liquidity pair found: {base_name}")
                pair_abi = [
                    {
                        "constant": True,
                        "inputs": [],
                        "name": "getReserves",
                        "outputs": [
                            {"name": "_reserve0", "type": "uint112"},
                            {"name": "_reserve1", "type": "uint112"},
                            {"name": "_blockTimestampLast", "type": "uint32"},
                        ],
                        "type": "function",
                    },
                ]
                pair_contract = web3.eth.contract(address=pair_address, abi=pair_abi)
                reserves = pair_contract.functions.getReserves().call()

                reserve_token = reserves[0] / (10 ** token_data["decimals"])
                reserve_base = reserves[1] / (10 ** 18)  # Assuming 18 decimals for base token

                token_price_base = reserve_base / reserve_token
                market_cap = token_data["total_supply"] * token_price_base

                return {
                    "base_token": base_name,
                    "liquidity_base": reserve_base,
                    "liquidity_token": reserve_token,
                    "market_cap_base": market_cap,
                }

        return "No liquidity pair found"
    except Exception as e:
        print(f"Error fetching liquidity and market cap: {e}")
        return None


# Fetch Holders using BscScan API
def fetch_holders(contract_address):
    try:
        url = f"https://api.etherscan.io/v2/api?module=account&action=tokentx&contractaddress={contract_address}&chainid=56&apikey={os.getenv('API_KEY_ETHERSCAN')}"

        # Log the API request
        # logging.info(f"Making API request to: {url}")

        response = requests.get(url).json()

        # Log the full API response for debugging
        # logging.info(f"API Response: {response}")

        if response.get("status") == "1" and "result" in response:
            transactions = response["result"]

            # Log the number of transactions found
            logging.info(f"Number of transactions found: {len(transactions)}")

            if transactions:
                # Extract unique holders
                unique_holders = set(tx["to"] for tx in transactions if tx["to"] and tx["to"] != "0x0000000000000000000000000000000000000000")

                # Log unique holders count
                logging.info(f"Unique holders: {len(unique_holders)}")
                return len(unique_holders)
            else:
                # No transactions mean 0 holders
                logging.info("No transactions found. Returning 0 holders.")
                return 0
        else:
            # Distinguish between no transactions and actual errors
            error_message = response.get("message", "Unknown error")
            if error_message == "No transactions found":
                logging.info("No transactions found. Returning 0 holders.")
                return 0
            else:
                logging.error(f"Error fetching holders data: {error_message}")
                return f"Error fetching holders data: {error_message}"
    except Exception as e:
        logging.exception(f"Error fetching holders: {e}")
        return None
    
# Fetch Burned Tokens
def fetch_burned_tokens(contract_address, burn_address="0x000000000000000000000000000000000000dead"):
    try:
        contract = load_token_contract(contract_address)
        if not contract:
            raise ValueError("Unable to load contract.")
        burned = contract.functions.balanceOf(Web3.to_checksum_address(burn_address)).call() / (10 ** contract.functions.decimals().call())
        return burned
    except Exception as e:
        logging.error(f"Error fetching burned tokens: {e}")
        return None


# Fetch Top 10 Holders
def fetch_top_holders(contract_address):
    try:
        url = f"https://api.bscscan.com/api?module=account&action=tokentx&contractaddress={contract_address}&chainid=56&apikey={os.getenv('API_KEY_BSCSCAN')}"
        response = requests.get(url).json()

        if response.get("status") == "1" and "result" in response:
            transactions = response["result"]
            holder_balances = {}

            for tx in transactions:
                to_address = tx["to"]
                from_address = tx["from"]
                value = int(tx["value"]) / (10 ** int(tx["tokenDecimal"]))

                # Update balances
                holder_balances[to_address] = holder_balances.get(to_address, 0) + value
                holder_balances[from_address] = holder_balances.get(from_address, 0) - value

            # Sort and get top 10 holders
            sorted_holders = sorted(holder_balances.items(), key=lambda x: x[1], reverse=True)
            return [{"address": holder[0], "balance": holder[1]} for holder in sorted_holders[:10]]
        else:
            return []
    except Exception as e:
        logging.error(f"Error fetching top holders: {e}")
        return None


# Fetch Taxes (Buy, Sell, Total)
def fetch_tax_info(contract_address):
    try:
        contract = load_token_contract(contract_address)
        if not contract:
            raise ValueError("Unable to load contract.")
        try:
            buy_tax = contract.functions.buyTax().call()  # Replace with the actual function name
            sell_tax = contract.functions.sellTax().call()  # Replace with the actual function name
        except:
            buy_tax = 0
            sell_tax = 0
            
        total_tax = buy_tax + sell_tax
        return {"buy_tax": buy_tax, "sell_tax": sell_tax, "total_tax": total_tax}
    except Exception as e:
        logging.error(f"Error fetching tax info: {e}")
        return None


# Estimate Gas (Gas 1 and Gas 2)
def estimate_gas(transaction):
    try:
        gas_estimate = web3.eth.estimate_gas(transaction)
        return gas_estimate
    except Exception as e:
        logging.error(f"Error estimating gas: {e}")
        return None


# Fetch Liquidity Percentage
def fetch_liquidity_percentage(liquidity_data, total_supply):
    try:
        liquidity_base = liquidity_data.get("liquidity_base", 0)
        liquidity_percentage = (liquidity_base / total_supply) * 100
        return liquidity_percentage
    except Exception as e:
        logging.error(f"Error calculating liquidity percentage: {e}")
        return None


# Classify Airdrops
def classify_airdrops(transactions):
    try:
        airdrops = []
        for tx in transactions:
            if int(tx["value"]) < 1 * 10**int(tx["tokenDecimal"]) and int(tx["txreceipt_status"]) == 1:
                airdrops.append(tx)
        return airdrops
    except Exception as e:
        logging.error(f"Error classifying airdrops: {e}")
        return None
