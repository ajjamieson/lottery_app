import os
import json
import boto3
import requests

def lambda_handler(event, context):
    """
    1. Fetch the PA Lottery Daily Evening Pick 3 from Magayo API.
    2. Parse the drawn number.
    3. Check if this number exists in a DynamoDB table.
    4. Log or send an email alert if it matches.
    """

    # -- 1) Fetch the PA Lottery Daily Evening Pick 3 from Magayo API --
    magayo_api_key = os.environ.get("MAGAYO_API_KEY", "")
    # According to Magayo docs, you need a "game_id" for your specific lottery game.
    # For example, let's assume the game ID for "PA Evening Pick 3" is "us_pa_pick3_eve".
    game_id = os.environ.get("MAGAYO_GAME_ID", "us_pa_pick3_eve")

    #api_url = f"https://api.magayo.com/results.php?api_key={magayo_api_key}&game_id={game_id}"
    api_url = f"https://www.magayo.com/api/results.php?api_key={magayo_api_key}&game={game_id}"

    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error calling Magayo API: {str(e)}")
        return {"statusCode": 500, "body": "Error calling Magayo API"}

    data = response.json()
    # The structure of the data depends on Magayo’s response format.
    # Typically, you'll see something like:
    # {
    #   "game_id": "us_pa_pick3_eve",
    #   "draw_date": "2025-01-01",
    #   "results": ["1", "2", "3"],
    #   "bonus": []
    #   ...
    # }
    # Adjust parsing as needed.

    if "results" not in data or not data["results"]:
        print("No results found in API response")
        return {"statusCode": 200, "body": "No results found"}

    # "results" might be a list of single digits, e.g. ["1","2","3"]
    # Join them to form "123"
    drawn_number = "".join(data["results"])
    print(f"Drawn Number: {drawn_number}")

    # -- 2) Check if the drawn_number exists in your DDB table --
    ddb_table_name = os.environ.get("DDB_TABLE_NAME", "LotteryNumbers")
    ddb_client = boto3.client("dynamodb")

    # We'll try to get the item by partition key = drawn_number
    try:
        ddb_response = ddb_client.get_item(
            TableName=ddb_table_name,
            Key={
                "lottery_number": {"S": drawn_number}
            }
        )
    except Exception as e:
        print(f"Error accessing DynamoDB: {str(e)}")
        return {"statusCode": 500, "body": "Error accessing DynamoDB"}

    # If 'Item' is present, that means someone has that number in the table
    if "Item" in ddb_response:
        name = ddb_response["Item"].get("name", {}).get("S", "Unknown")
        print(f"Match found! Number {drawn_number} belongs to {name}.")
        email_body = f"The winning number is {drawn_number}, and it belongs to {name}."
    else:
        email_body = f"The winning number is {drawn_number}, but no matches were found."
        print(f"No match found for number {drawn_number}.")

    ses_client = boto3.client('ses', region_name='us-east-1')
    ses_client.send_email(
        Source="alexander.jamieson@gmail.com",
        Destination={'ToAddresses': ["alexander.jamieson@gmail.com"]},
        Message={
            'Subject': {'Data': "PA Lottery Evening Pick 3 Results"},
            'Body': {'Text': {'Data': email_body}}
        }
    )

    return {
            "statusCode": 200,
            "body": email_body
        }
