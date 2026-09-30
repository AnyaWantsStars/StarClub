"""
排名/公示计算服务
统一三处排名计算逻辑：签到排行、公示详情、公示预览
"""


def compute_ranking(records, show_records=True):
    """
    从记录列表计算排名。

    参数:
        records: dict 列表，每个 dict 包含 user_id, username, duration_minutes
        show_records: 是否在排名中包含详细记录列表

    返回:
        rankings: 排名列表，每项包含 rank, user_id, username, total_minutes, duration_str, [records]
    """
    user_durations = {}
    for r in records:
        uid = r['user_id']
        if uid not in user_durations:
            user_durations[uid] = {
                'user_id': uid,
                'username': r['username'],
                'total_minutes': 0,
                'records': []
            }
        user_durations[uid]['total_minutes'] += r['duration_minutes']
        if show_records:
            user_durations[uid]['records'].append(r)

    rankings = sorted(user_durations.values(), key=lambda x: x['total_minutes'], reverse=True)
    for i, r in enumerate(rankings):
        r['rank'] = i + 1
        hours = int(r['total_minutes'] // 60)
        mins = int(r['total_minutes'] % 60)
        r['duration_str'] = f"{hours}小时{mins}分钟"

    return rankings


def filter_records_for_ranking(records, start_date, end_date, valid_only=True,
                               include_users=None, exclude_users=None):
    """
    通用签到记录过滤函数。

    返回过滤后的 dict 列表，每项含 user_id, username, duration_minutes 等。
    """
    result = []
    for record in records:
        if valid_only and record.status != 'valid':
            continue

        record_date = record.check_in[:10]
        if record_date < start_date or record_date > end_date:
            continue

        if include_users and record.user_id not in include_users:
            continue

        if exclude_users and record.user_id in exclude_users:
            continue

        result.append({
            'user_id': record.user_id,
            'username': record.username,
            'duration_minutes': record.get_duration_minutes(),
            **record.to_dict()
        })
    return result