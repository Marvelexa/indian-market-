import sys
sys.path.append('scratch')
from test_scaled_performance import res_df

crude_trades = res_df[res_df['symbol'] == 'CRUDEOIL']
print("CRUDE OIL TRADES IN TEST_SCALED_PERFORMANCE:")
print(crude_trades[['date', 'entry_time', 'action', 'mode', 'entry_price', 'exit_price', 'pnl', 'reason']])
