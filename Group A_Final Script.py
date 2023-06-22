#!/usr/bin/env python
# coding: utf-8

# In[ ]:


# Import relevant libraries
import yahoo_fin.options as ops
import os
import yahoo_fin.stock_info as si
import opstrat as op
import datetime
import pandas as pd
from optionprice import Option
from dateutil import parser
import streamlit as st
st.set_option('deprecation.showPyplotGlobalUse', False)


st.header("Option Trading with Opstrat")
st.subheader("Welcome to the Option Trading application.\nThis app shows you the cash payouts for buying or selling one contract of 100 shares for both a call and put option")



# Get today's date
today = datetime.date.today()
todaysDate = today.strftime('%m/%d/%Y')

#try clause keeps streamlit from trying to run without all input
try:
	# User enters stock for options trading
	stock = st.text_input("Enter stock ticker").upper()
	daily = si.get_data(stock, start_date="04/26/2022", end_date=todaysDate, index_as_date = True, interval="1d")
	today = daily.iloc[-1]
	spot = today[3]
	dividend = si.get_dividends(stock)
	try:
		div = dividend['dividend'][-1]
	except:
		div = 0


	# Get expiry dates of stock options from input
	expirationDates = ops.get_expiration_dates(stock)
	expirationDatesdf = pd.DataFrame(expirationDates, columns=['Expiration Dates'])



	# User enter's option date of choice
	optionDate = st.selectbox('Click a date from above that you\'d like to exercise an options trade(s)\n>>>',expirationDatesdf['Expiration Dates'])


	# Format expiry date to mm/dd/yyyy

	dateObj = parser.parse(optionDate)
	formattedExpiryDate = dateObj.strftime("%m/%d/%Y")




	## Data Allocation

	# Get call options of stock for provided expiry date
	calls = ops.get_calls(stock,optionDate)
	calls.set_index("Contract Name",inplace = True)
   
	# Get put options of stock for provided expiry date
	puts = ops.get_puts(stock,optionDate)
	puts.set_index("Contract Name",inplace = True)

	strike = st.selectbox('Click a strike price that you\'d like to sell an options trade(s)\n>>>', puts['Strike'])

	trxnType = st.selectbox("Would you like to take a short or long position?",("Short","Long"))
	if trxnType == "Short":
		trxType = 's'
	else:
		trxType = 'b'


	#Difference in days between Expiry Date and Today's Date

	date_format = "%m/%d/%Y"
	date1 = datetime.datetime.strptime(todaysDate, date_format)
	date2 = datetime.datetime.strptime(formattedExpiryDate, date_format)



	# Calculate the difference
	timedelta = date2 - date1

	# Convert the difference to a number of days
	days = timedelta.days


	# ### Get Treasury rate for determining option price



	url = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve&field_tdr_date_value=2023"


	dfs = pd.read_html(url)

	df = dfs[0]




	# Treasury Rate is given by a range of 1 Month to 10 Years.
	# This cell maps this range into days from months and years.  Rates are now represented by a number of days,
	# and the code below fits the closest bucket of days to the number of days until expiry to determine the most
	# appropriate rate to determine the option price

	############## Start of Data Wrangling ####################
	exclude_start = 1
	exclude_end = 9

	selected_columns = df.iloc[:, [*range(exclude_start), *range(exclude_end + 1, df.shape[1])]]

	selected_columns.set_index('Date',inplace = True)
	treasuryRateChart = selected_columns.tail(1).transpose()

	newIndex = [30,60,90,120,180,365,365*2,365*3,365*5,365*7,365*10,365*20,365*30]

	treasuryRateChart.index = newIndex

	newColumnName = ['Rates']
	treasuryRateChart.columns = newColumnName
	treasuryRateChart.index.name = 'Days'

	############### End of Data Wrangling ##################

	# Finds the best fit rate based on the number of days until expiry 
	closestIndex = min(treasuryRateChart.index, key=lambda x: abs(x - days))
	closestValue = treasuryRateChart.loc[closestIndex,'Rates']


	### Call Option



	# Get data from call option based on expiry date and strike price
	call = calls[calls['Strike'] == strike]
	call = call.to_dict(orient='records')[0]




	#Get implied volatility from option
	percentage_float = float(call['Implied Volatility'].strip('%'))/100



	## Code from Code from https://sanketkarve.net/automating-option-pricing-calculations/ ##
	#Define option
	option_det = Option(european=True,
						kind='call',
						s0=spot,
						k=strike,
						t=days,
						sigma=percentage_float,
						r= (closestValue/100),
						dv=div)



	## End of Code from Code from https://sanketkarve.net/automating-option-pricing-calculations/ ##

	# Get option price
	priceCall = option_det.getPrice(method='BSM',iteration=5000)



	ploss = {'Equity Market Price at Expiry': [spot*.7,spot*.8,spot*.9,
											   spot,spot*1.1,spot*1.2,spot*1.3]}
	## Ask for number of contracts
	sperc = 100*1 #100 shares per contract
	df = pd.DataFrame(ploss, columns = ['Equity Market Price at Expiry','Call P/L'])
	payoffs = []
	for i in df['Equity Market Price at Expiry']:

	# Calculate Option Payoffs
			payoff = max(((i - strike) * sperc) - (priceCall*sperc),-priceCall*sperc)
			if trxType == 's':
				payoff = payoff*-1
				payoffs.append(payoff)
			else:
				payoffs.append(payoff)

	# Create DataFrame
	ploss['Call P/L']=payoffs
	final1=pd.DataFrame(ploss,columns=['Equity Market Price at Expiry','Call P/L'])
	final1['% Change'] = ['-30%','-20%','-10%','0%','+10%','+20%','+30%']


	# Plot Option
	fig1 = op.single_plotter(spot=spot, strike=strike, op_type='c', tr_type=trxType, op_pr=priceCall,spot_range = 100)
	st.pyplot(fig1)
	final1.set_index('% Change',inplace = True)
	final1
	# ### Put Option



	# Get data from put option based on expiry date and strike price
	put = puts[puts['Strike'] == strike]
	put = put.to_dict(orient='records')[0]




	#Get implied volatility from option
	percentage_float = float(put['Implied Volatility'].strip('%'))/100



	## Code from Code from https://sanketkarve.net/automating-option-pricing-calculations/ ##

	# Define option and get option price 
	option_det = Option(european=True,
						kind='put',
						s0=spot,
						k=strike,
						t=days,
						sigma=percentage_float,
						r=closestValue/100,
						dv=div)

	pricePut = option_det.getPrice(method='BSM',iteration=5000)
	## End of Code from Code from https://sanketkarve.net/automating-option-pricing-calculations/ ##


	# Get payouts of Put option based off probable equity prices at expiry
	ploss = {'Equity Market Price at Expiry': [spot*.7,spot*.8,spot*.9,
											   spot,spot*1.1,spot*1.2,spot*1.3]}
	sperc = 100*1 #100 shares per contract
	df = pd.DataFrame(ploss, columns = ['Equity Market Price at Expiry','Put P/L'])
	payoffs = []
	for i in df['Equity Market Price at Expiry']:

	# Calculate Option Payoffs
			payoff = max(((strike - i) * sperc) - (pricePut*sperc),-pricePut*sperc)
			if trxType == 's':
				payoff = payoff*-1
				payoffs.append(payoff)
			else:
				payoffs.append(payoff)

	# Create DataFrame
	ploss['Put P/L']=payoffs
	final2=pd.DataFrame(ploss,columns=['Equity Market Price at Expiry','Put P/L'])
	final2['% Change'] = ['-30%','-20%','-10%','0%','+10%','+20%','+30%']

	fig2 = op.single_plotter(spot=spot, strike=strike, op_type='p', tr_type=trxType, op_pr=pricePut,spot_range = 100)
	st.pyplot(fig2)
	final2.set_index('% Change',inplace = True)
	final2
	# ### Multi Plot



	# Join PLs from Call and Put
	final1 = final1[['Equity Market Price at Expiry','Call P/L']]
	final2 = final2[['Put P/L']]
	result = pd.merge(final1, final2,on = '% Change' ,how='left')
	#result.fillna(0,inplace = True)
	result['Total P/L'] = result.sum(axis=1)
	

	# Plot Put and Call
	op1={'op_type': 'p', 'strike': strike, 'tr_type': trxType, 'op_pr': pricePut}
	op2={'op_type': 'c', 'strike': strike, 'tr_type': trxType, 'op_pr': priceCall}

	op_list=[op1, op2]
	fig3= op.multi_plotter(spot=spot, op_list=op_list,spot_range = 100)
	st.pyplot(fig3)
	result
except:
	print('Loading')
