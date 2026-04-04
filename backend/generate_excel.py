import pandas as pd
import random
from datetime import datetime, timedelta

def main():
    random.seed(42)
    parties = ['Acme Corp', 'Globex', 'Soylent', 'Initech', 'Umbrella']
    data = []
    date = datetime(2022, 4, 1)

    for i in range(150):
        data.append({
            'transaction_date': date + timedelta(days=random.randint(0, 365)),
            'party': random.choice(parties),
            'items': random.randint(1, 100),
            'revenue': round(random.uniform(500, 15000), 2),
            'product_name': f'Product_{random.randint(1, 5)}',
            'transaction_id': f'TXN_{1000+i}'
        })

    df = pd.DataFrame(data)
    df.to_excel('sr_22-23.xlsx', index=False)
    print("Test file sr_22-23.xlsx generated successfully.")

if __name__ == "__main__":
    main()
