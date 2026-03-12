for i, l in enumerate(open('core/rpc_service.py', encoding='utf-8')):
    if 'def handle_request' in l: print(i)
