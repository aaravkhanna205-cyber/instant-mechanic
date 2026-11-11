export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
export type Account = {id:string;email:string;full_name:string;is_platform_admin:boolean;memberships:{organization_id:string;role:string}[]};
export type Organization = {id:string;name:string;slug:string};
export type Job = {id:string;organization_id:string;title:string;category_slug:string;description:string;location:string|null;status:string;created_at:string|null};
export type Application = {id:string;job_id:string;candidate_id:string;stage:string;applied_at:string|null};
export type Candidate = {id:string;full_name:string;email:string;city:string|null;skills:Record<string,unknown>};
export type Interview = {id:string;application_id:string;status:string;scheduled_at:string|null};
export type Category = {slug:string;title:string;department:string};
export type AdminUser = {id:string;email:string;full_name:string;active:boolean;is_platform_admin:boolean};
export type ImportBatch = {id:string;filename:string;status:string;created_at:string};
export type AppSetting = {key:string;value:unknown};
export type Session = {user:Account;csrf_token:string};
export class ApiError extends Error {constructor(public status:number,message:string){super(message);}}
export async function api<T>(path:string, options:RequestInit={}, csrf=""):Promise<T>{
 const headers = new Headers(options.headers || {});
 if(options.body && !(options.body instanceof FormData)) headers.set("Content-Type","application/json");
 if(csrf) headers.set("X-CSRF-Token",csrf);
 let response:Response;
 try {response=await fetch(`${API_URL}${path}`,{...options,headers,credentials:"include",cache:"no-store"});}
 catch {throw new ApiError(0,"Cannot reach FastAPI. Check the backend address and CORS settings.");}
 let data:unknown=null;
 try{data=await response.json();}catch{ /* 204 or non-JSON error */ }
 if(!response.ok){const d=data as {detail?:unknown}|null;const detail=d?.detail;throw new ApiError(response.status,typeof detail==="string"?detail:JSON.stringify(detail??data??response.statusText));}
 return data as T;
}
export const encoded = (id:string)=>encodeURIComponent(id);
