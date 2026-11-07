// Only read-only Dashboard, Devices and Users pages include this module.
// Forms and map/history editors retain their own state and are not reloaded.
const initial=JSON.parse(document.getElementById('live-revision').textContent);
let pending=false;
async function check(){
  if(pending||document.hidden)return;
  const focused=document.activeElement;
  if(focused?.matches('input,textarea,select,[contenteditable="true"]'))return;
  pending=true;
  try{
    const response=await fetch('/sync-status/',{cache:'no-store',headers:{Accept:'application/json'}});
    if(!response.ok||response.redirected)return;
    const current=await response.json();
    if(current.revision!==initial)window.location.reload();
  }catch(error){/* Keep the last displayed data until connectivity returns. */}
  finally{pending=false;}
}
setInterval(check,10000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)check();});
window.addEventListener('online',check);
check();
