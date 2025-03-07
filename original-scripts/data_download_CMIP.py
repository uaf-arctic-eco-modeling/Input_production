import cdsapi
import requests
import os



### storage directory
cmipdir = os.getenv('cmipdir')
### CMIP version
cmipversion = os.getenv('cmipversion')
### List of models
gcmlist = os.getenv('gcm_list').split(',')
### List of scenarios
sclist = os.getenv('sc_list').split(',')
### List of variables
varlist = os.getenv('var_list').split(',')



### This suite of download is part of the model comparison with historical climate product to document model selection. 

c = cdsapi.Client()

for sc in sclist:
    print(sc)
    for gcm in gcmlist:
        print(gcm)
        for var in varlist:
            print(var)
            c.retrieve(
                str('projections-cmip' + cmipversion),
                {
                    'format': 'zip',
                    'temporal_resolution': 'daily',
                    'experiment': sc,
                    'variable': var,
                    'year': ['2015', '2016', '2017',
                        '2018', '2019', '2020',
                        '2021', '2022', '2023',
                        '2024', '2025', '2026',
                        '2027', '2028', '2029',
                        '2030', '2031', '2032',
                        '2033', '2034', '2035',
                        '2036', '2037', '2038',
                        '2039', '2040', '2041',
                        '2042', '2043', '2044',
                        '2045', '2046', '2047',
                        '2048', '2049', '2050',
                        '2051', '2052', '2053',
                        '2054', '2055', '2056',
                        '2057', '2058', '2059',
                        '2060', '2061', '2062',
                        '2063', '2064', '2065',
                        '2066', '2067', '2068',
                        '2069', '2070', '2071',
                        '2072', '2073', '2074',
                        '2075', '2076', '2077',
                        '2078', '2079', '2080',
                        '2081', '2082', '2083',
                        '2084', '2085', '2086',
                        '2087', '2088', '2089',
                        '2090', '2091', '2092',
                        '2093', '2094', '2095',
                        '2096', '2097', '2098',
                        '2099', '2100'],
                    'month': ['01', '02', '03',
                        '04', '05', '06',
                        '07', '08', '09',
                        '10', '11', '12'],
                    'day': ['01', '02', '03',
                        '04', '05', '06',
                        '07', '08', '09',
                        '10', '11', '12',
                        '13', '14', '15',
                        '16', '17', '18',
                        '19', '20', '21',
                        '22', '23', '24',
                        '25', '26', '27',
                        '28', '29', '30',
                        '31'],
                    'area': [90, -180, 30,180],
                    'model': gcm,
                },
                os.path.join(cmipdir,'CMIP' + cmipversion + '_' + sc + '_' + gcm + '_' + var + '.zip'))




