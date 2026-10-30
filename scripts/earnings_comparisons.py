"""Same-basis financial comparison display; callers own verified source/basis inputs."""
def compare(current, previous, *, margin=False):
    if not isinstance(current, (int,float)) or isinstance(current,bool) or not isinstance(previous,(int,float)) or isinstance(previous,bool):
        return '미확인', None
    if margin:
        d=current-previous
        return f'{d:+.2f}pp', d
    if previous > 0 and current < 0:
        return '적자 전환', None
    if previous > 0:
        d=(current/previous-1)*100
        return f'{d:+.2f}%', d
    if previous == 0:
        return ('변동 없음' if current == 0 else '흑자 전환' if current > 0 else '적자 전환'), None
    if current >= 0:
        return ('손익분기' if current == 0 else '흑자 전환'), None
    return ('적자 축소' if current>previous else '적자 확대' if current<previous else '변동 없음'), None


def normalize_metric(metric):
    raw=metric.get('raw',{})
    rate=metric.get('label') in ('매출총이익률','영업이익률','GPM','OPM')
    for field,base in [('yoy','yearAgoQuarter'),('qoq','previousQuarter')]:
        if raw.get('value') is None or raw.get(base) is None:
            continue
        metric[field], numeric=compare(raw['value'],raw[base],margin=rate)
        raw[field+('Pp' if rate else 'Pct')]=numeric
    return metric
