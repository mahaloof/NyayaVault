export const API=process.env.NEXT_PUBLIC_API_URL||'http://127.0.0.1:8000/api';
export async function api(path:string,options:RequestInit={}){
 const token=typeof window!=='undefined'?sessionStorage.getItem('nv-token'):null;
 const response=await fetch(API+path,{...options,headers:{...(token?{Authorization:`Bearer ${token}`} : {}),...(!(options.body instanceof FormData)?{'Content-Type':'application/json'}:{}),...options.headers}});
 if(!response.ok){let message='Unable to complete request';try{const data=await response.json();message=typeof data.detail==='string'?data.detail:JSON.stringify(data.detail)}catch{};throw new Error(message)}
 return response.json();
}
export function date(value:string){return new Date(value).toLocaleString()}
