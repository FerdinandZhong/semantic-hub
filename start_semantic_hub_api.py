"""Serve only the published semantic consumer API. Studio routes are not mounted."""
import argparse
import os
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'shared'))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir',type=Path,required=True)
    access=parser.add_mutually_exclusive_group(required=True)
    access.add_argument('--api-token-file',type=Path,help='Optional bearer authentication for a hosted demo')
    access.add_argument('--local-no-auth',action='store_true',help='Run without a consumer token on loopback only')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8086)
    parser.add_argument('--model-token-file',type=Path,help='Optional OpenAI credential for inherited embedding configuration')
    args=parser.parse_args()
    if args.local_no_auth:
        if args.host not in ('127.0.0.1','::1','localhost'):
            parser.error('--local-no-auth requires a loopback host')
        os.environ.pop('SEMANTIC_HUB_API_TOKEN',None)
    else:
        token=args.api_token_file.expanduser().read_text().strip()
        if len(token)<32:parser.error('Use a consumer token of at least 32 characters.')
        os.environ['SEMANTIC_HUB_API_TOKEN']=token
    os.environ['HELIOS_DEMO_STATE']=str(args.state_dir.resolve())
    if args.model_token_file:
        credential=args.model_token_file.expanduser().read_text().strip()
        if not credential:parser.error('The model credential file is empty.')
        os.environ.update(LLM_PROVIDER='openai',INFERENCE_BASE_URL='https://api.openai.com/v1',
                          INFERENCE_MODEL='gpt-4o',INFERENCE_TOKEN=credential)
    import uvicorn
    from apps.helios.console.semantic_hub_api import create_application
    uvicorn.run(create_application(local_no_auth=args.local_no_auth),host=args.host,port=args.port)

if __name__=='__main__':main()
