import argparse
import os
import sys
import shutil
import subprocess
import re
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import pickle
import itertools
import io

tables = {}

teams = ['ANA','ATL','BAL','BOS','BRK','BUF','CAP','CAR','CHA','CHH','CHI','CHO','CHP','CHZ','CIN',\
         'CLE','DAL','DEN','DET','DLC','DNA','DNR','FLO','FTW','GSW','HOU','HSM','INA','IND','KCK','KCO',\
         'KEN','LAC','LAL','LAS','MEM','MIA','MIL','MIN','MLH','MMF','MMP','MMS','MMT','MNL','MNM','MNP',\
         'NYA','NJA','NJN','NOB','NOH','NOJ','NOK','NOP','NYK','NYN','OAK','OKC','ORL','PHI','PHO','PHW','POR',\
         'PTC','PTP','ROC','SAA','SAC','SAS','SDA','SDC','SDR','SDS','SEA','SFW','SSL','STL','SYR',\
         'WSC','TEX','TOR','TRI','UTA','UTS','VAN','VIR','WAS','WSA','WSB','BLB','INO']
teams = sorted(teams)

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--year', default=2019,type=int, help='season to save')
parser.add_argument('--folder', default='teams',type=str, help='folder to save year stats')
parser.add_argument('--cfolder', default='contracts',type=str, help='contracts folder')
parser.add_argument('--offolder', default='onoff',type=str, help='onoff folder')
parser.add_argument('--tfolder', default='trans',type=str, help='trans folder')
parser.add_argument('--ow', action='store_true',help='overwrite existing')
parser.add_argument('--process', action='store_true',help='only process files, no fetching')

args = parser.parse_args()

for folder in [args.folder,args.cfolder,args.offolder,args.tfolder]:
    try:
        os.mkdir(folder)
        print("Directory {} created".format(folder))
    except FileExistsError:
        pass


for team in teams:
    target = os.path.join(args.folder,team + str(args.year) + '.html')
    ctarget = os.path.join(args.cfolder,team + '.html')
    otarget = os.path.join(args.offolder,team + str(args.year) + '.html')
    ttarget = os.path.join(args.tfolder,team + str(args.year) + '.html')

    if args.process:
        if not os.path.exists(target):
            continue
    # get the files
    else:
        if args.ow or not os.path.exists(target):
            subprocess.call(['wget','-O',target,
            'https://www.basketball-reference.com/teams/{}/{}.html'.format(team,args.year)])
            fs = os.path.getsize(target)
            if fs < 10:
                os.remove(target)
                continue
        if args.ow or not os.path.exists(otarget):
            subprocess.call(['wget','-O',otarget,
            'https://www.basketball-reference.com/teams/{}/{}/on-off/'.format(team,args.year)])
        if args.ow or not os.path.exists(ctarget):
            subprocess.call(['wget','-O',ctarget,
            'https://www.basketball-reference.com/contracts/{}.html'.format(team)])
        if args.ow or not os.path.exists(ttarget):
            subprocess.call(['wget','-O',ttarget,
            'https://www.basketball-reference.com/teams/{}/{}_transactions.html'.format(team,args.year)])

    # load the data
    try:
        with open(target,'rt') as fp:
            data = fp.read()
    except:
        with open(target,'rt',encoding='latin-1') as fp:
            data = fp.read()
    try:
        with open(ctarget,'rt') as fp:
            datac = fp.read()
        with open(otarget,'rt') as fp:
            datao = fp.read()
    except:
        with open(ctarget,'rt',encoding='latin-1') as fp:
            datac = fp.read()
        with open(otarget,'rt',encoding='latin-1') as fp:
            datao = fp.read()
    # collect all the tables
    m = re.findall(r'<!--[ \n]*(<div[\s\S\r]+?</div>)[ \n]*-->',data)
    m2 = re.findall(r'(<div class="table_outer_container">[ \n]*<div class="overthrow table_container" id="div_roster">[\s\S\r]+?</table>[ \n]*</div>[ \n]*</div>)',data)
    m3 = re.findall(r'(<div class="table_outer_container">[ \n]*<div class="overthrow table_container" id="div_contracts">[\s\S\r]+?</table>[ \n]*</div>[ \n]*</div>)',datac)
    m4 = re.findall(r'<!--[ \n]*(<div[\s\S\r]+?</div>)[ \n]*-->',datao)

    m = m2 + m + m3 + m4
    print(target,len(m),len(m4))
    tables[team] = {}

    bs = BeautifulSoup(data,features="lxml")

    tables[team]['logo'] = re.findall('(http.*png)',str(bs.find_all('img',{"class": "teamlogo"})[0]))[0]
    tables[team]['name'] = re.findall('{}-{} (.*) Roster and Stats'.format(args.year-1,str(args.year)[-2:]),data)[0]
    tables[team]['conf'] = re.findall('<p>[ \n]*<strong>Record:<\/strong>[ \n]*(.*)*\n.*[ \n]*<\/p>',data)[0]

    for test_table in m:
        try:
            soup = BeautifulSoup(test_table,features="lxml")
            table_id = str(soup.find('table').get('id'))

            if table_id == ['team_and_opponent']:
                continue
            soup.findAll('tr')

            table_size = {'on_off':1,'on_off_p':1,'shooting':2,'pbp':1,'playoffs_shooting':2,'playoffs_pbp':1,'contracts':1}

            # use getText()to extract the text we need into a list
            headers = [th.getText() for th in soup.findAll('tr')[table_size.get(table_id,0)].findAll('th')]

            # exclude the first column as we will not need the ranking order from Basketball Reference for the analysis
            start_col = 1
            if table_id in ['contracts','injury','on_off','on_off_p']:
                start_col = 0

            headers = headers[start_col:]
            rows = soup.findAll('tr')[start_col:]
            player_stats = [[td.getText() for td in rows[i].findAll('td')]
                        for i in range(len(rows))]

            if table_id in ['contracts']:
                player_status = [[td.get('class') for td in rows[i].findAll('td')]
                        for i in range(len(rows))]
                status_array = []
                for status in player_status:
                    if len(status) > 0:
                        s2 = [False] + [s[-1] in ['salary-pl','salary-et','salary-tm'] for s in status[1:]]
                    else:
                        s2 = np.array([])
                    status_array.append(s2)
                status_array = np.array(status_array)
                player_stats_new = []
                for a,b in zip(status_array,player_stats):
                    b_new = []
                    for c,d in zip(a,b):
                        b_new.append(d if not c else '')
                    player_stats_new.append(b_new)
                player_stats = player_stats_new
            if table_id in ['contracts','injury','on_off','on_off_p']:
                player_names = [[td.getText() for td in rows[i].findAll('th')]
                            for i in range(len(rows))]
                player_stats = [a + b for a,b in zip(player_names[1:],player_stats[1:])]
            headers[0] = 'Name'
            stats = pd.DataFrame(player_stats, columns = headers).set_index('Name')
            if table_id in ['contracts']:
                stats = stats.drop(['Player'])
                stats = stats.iloc[:stats.index.get_loc('')]

            # drop nan
            stats = stats[~ stats.index.isin([None])]
            # convert to float
            obj_cols = stats.loc[:, stats.dtypes == object]
            conv_cols = obj_cols.apply(pd.to_numeric, errors = 'ignore')
            stats.loc[:, stats.dtypes == object] = conv_cols

            stats = stats.fillna('')

            if True and 'on_off' in table_id:
                stats = stats.iloc[~ stats.index.get_loc('Player')]
                stats = stats.loc[~ (stats.Split == '')]
                stats.index = list(itertools.chain.from_iterable(itertools.repeat(x, 3) for x in [_ for _ in stats.index if _!='']))

            #print(table_id,stats.index)
            tables[team][table_id]= stats
        except KeyboardInterrupt:
            raise
        except:
            pass
            #print('FAILED TO PARSE ' +str(soup.find('table').get('id') ))
with open('tables_{}.pkl'.format(args.year),'wb') as fp:
    pickle.dump(tables,fp)
