import requests
city = 'Bangalore'
api_url = 'https://api.api-ninjas.com/v1/airquality?city=Bangalore'.format(city)
response = requests.get(api_url, headers={'X-Api-Key': 'kOH3JYsrXfjK6WZuipwD5g==yasfwFJGpnZlphKq'})
if response.status_code == requests.codes.ok:
    print(response.text)
else:
    print("Error:", response.status_code, response.text)