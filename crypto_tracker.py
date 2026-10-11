import requests

url = "https://api.coingecko.com/api/v3/simple/price"

params = {
    "ids": "bitcoin,ethereum,dogecoin,solana",
    "vs_currencies": "usd"
}

response = requests.get(url, params=params)

if response.status_code == 200:
    data = response.json()

    print("\nCryptocurrency Price Tracker")
    print("----------------------------")

    print("Bitcoin  :", "$", data["bitcoin"]["usd"])
    print("Ethereum :", "$", data["ethereum"]["usd"])
    print("Dogecoin :", "$", data["dogecoin"]["usd"])
    print("Solana   :", "$", data["solana"]["usd"])

else:
    print("Unable to fetch cryptocurrency prices.")