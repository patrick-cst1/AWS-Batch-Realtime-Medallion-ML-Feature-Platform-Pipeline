"""
Generate Synthetic Batch Data
Author: Patrick Cheung

Generates synthetic card transaction data for testing the pipeline.
"""

import json
import random
import time
from datetime import datetime, timedelta
import boto3
from typing import List, Dict


class SyntheticDataGenerator:
    """
    Generate synthetic card transaction data
    """
    
    def __init__(self, num_cards: int = 100, num_merchants: int = 50):
        self.num_cards = num_cards
        self.num_merchants = num_merchants
        self.card_ids = [f"card_{i:05d}" for i in range(num_cards)]
        self.merchant_ids = [f"merchant_{i:04d}" for i in range(num_merchants)]
        self.currencies = ["USD", "EUR", "GBP", "JPY", "SGD"]
        self.countries = ["US", "UK", "SG", "JP", "DE", "FR"]
        self.pos_modes = ["chip", "contactless", "swipe", "online"]
    
    def generate_transaction(self, timestamp: datetime = None) -> Dict:
        """
        Generate a single transaction
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        transaction = {
            "event_id": f"evt_{int(timestamp.timestamp())}_{random.randint(1000, 9999)}",
            "card_id": random.choice(self.card_ids),
            "ts": int(timestamp.timestamp()),
            "merchant_id": random.choice(self.merchant_ids),
            "amount": round(random.uniform(5.0, 2000.0), 2),
            "currency": random.choice(self.currencies),
            "country": random.choice(self.countries),
            "pos_mode": random.choice(self.pos_modes)
        }
        
        return transaction
    
    def generate_batch(self, num_transactions: int, start_time: datetime = None) -> List[Dict]:
        """
        Generate a batch of transactions
        """
        if start_time is None:
            start_time = datetime.utcnow()
        
        transactions = []
        for i in range(num_transactions):
            # Spread transactions over time (within 1 minute)
            timestamp = start_time + timedelta(seconds=random.uniform(0, 60))
            transaction = self.generate_transaction(timestamp)
            transactions.append(transaction)
        
        return transactions
    
    def save_to_file(self, transactions: List[Dict], filename: str):
        """
        Save transactions to a JSON file
        """
        with open(filename, 'w') as f:
            for txn in transactions:
                f.write(json.dumps(txn) + '\n')
        
        print(f"Saved {len(transactions)} transactions to {filename}")
    
    def send_to_kinesis(self, transactions: List[Dict], stream_name: str, region: str = "ap-southeast-1"):
        """
        Send transactions to Kinesis Data Stream
        """
        client = boto3.client('kinesis', region_name=region)
        
        success_count = 0
        error_count = 0
        
        for txn in transactions:
            try:
                response = client.put_record(
                    StreamName=stream_name,
                    Data=json.dumps(txn),
                    PartitionKey=txn['card_id']
                )
                success_count += 1
                
                if success_count % 100 == 0:
                    print(f"Sent {success_count} records...")
                
            except Exception as e:
                print(f"Error sending record: {e}")
                error_count += 1
        
        print(f"Kinesis ingestion complete: {success_count} success, {error_count} errors")


def generate_single_transaction(card_id: str = None, timestamp: datetime = None) -> Dict:
    """
    Helper function to generate a single transaction with optional card_id.
    """
    generator = SyntheticDataGenerator()
    if timestamp is None:
        timestamp = datetime.utcnow()
    
    transaction = generator.generate_transaction(timestamp)
    if card_id:
        transaction["card_id"] = card_id
    
    return transaction


def validate_transaction(txn: Dict) -> bool:
    """
    Validate a transaction has all required fields and valid values.
    """
    required_fields = ["event_id", "card_id", "ts", "merchant_id", "amount", "currency", "country", "pos_mode"]
    
    # Check all required fields exist
    for field in required_fields:
        if field not in txn:
            return False
    
    # Check amount is positive
    if txn["amount"] <= 0:
        return False
    
    return True


def main():
    """
    Main function to generate and send synthetic data
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate synthetic transaction data")
    parser.add_argument("--num-transactions", type=int, default=1000, help="Number of transactions to generate")
    parser.add_argument("--num-cards", type=int, default=100, help="Number of unique cards")
    parser.add_argument("--num-merchants", type=int, default=50, help="Number of unique merchants")
    parser.add_argument("--output-file", type=str, help="Output JSON file")
    parser.add_argument("--kinesis-stream", type=str, help="Kinesis stream name")
    parser.add_argument("--region", type=str, default="ap-southeast-1", help="AWS region")
    parser.add_argument("--continuous", action="store_true", help="Continuously generate data")
    parser.add_argument("--rate", type=int, default=10, help="Transactions per second (for continuous mode)")
    
    args = parser.parse_args()
    
    # Initialize generator
    generator = SyntheticDataGenerator(
        num_cards=args.num_cards,
        num_merchants=args.num_merchants
    )
    
    if args.continuous:
        # Continuous mode
        print(f"Starting continuous generation at {args.rate} TPS")
        
        while True:
            batch = generator.generate_batch(args.rate)
            
            if args.kinesis_stream:
                generator.send_to_kinesis(batch, args.kinesis_stream, args.region)
            
            if args.output_file:
                generator.save_to_file(batch, args.output_file)
            
            time.sleep(1)  # Wait 1 second
    
    else:
        # One-time batch generation
        print(f"Generating {args.num_transactions} transactions")
        transactions = generator.generate_batch(args.num_transactions)
        
        if args.output_file:
            generator.save_to_file(transactions, args.output_file)
        
        if args.kinesis_stream:
            generator.send_to_kinesis(transactions, args.kinesis_stream, args.region)
        
        if not args.output_file and not args.kinesis_stream:
            print("No output specified. Use --output-file or --kinesis-stream")
            print(f"Sample transaction: {json.dumps(transactions[0], indent=2)}")


if __name__ == "__main__":
    main()
