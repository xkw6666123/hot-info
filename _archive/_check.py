import json
with open('data.json','r',encoding='utf-8') as f:
    data = json.load(f)
bloggers = [a for a in data['articles'] if a.get('source')=='blogger']
print('Total blogger videos:', len(bloggers))
from collections import Counter
for name, cnt in Counter(a.get('blogger_name','') for a in bloggers).most_common():
    vids = [a for a in bloggers if a.get('blogger_name')==name]
    dates = sorted([a.get('date','') for a in vids], reverse=True)
    print(name + ': ' + str(cnt) + ' latest=' + dates[0] + ' all=' + str(dates))
