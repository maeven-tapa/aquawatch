const list=document.getElementById('alerts-list'),status=document.getElementById('alerts-sync-status');
const token=document.querySelector('#alert-csrf input').value;
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text)e.textContent=text;if(cls)e.className=cls;return e;};
let refreshing=false,dismissing=false,signature,generation=0;
function render(alerts) {
  if(!alerts.length){const empty=node('div',undefined,'empty-state');empty.append(node('strong','No active alerts'),node('p','New incidents and device warnings will appear here.'));list.replaceChildren(empty);return;}
  const items=node('ul',undefined,'item-list');
  for(const alert of alerts){
    const item=node('li');item.dataset.alertId=alert.server_id;
    const heading=node('div',undefined,'item-heading');
    const level=['critical','high','medium','low'].includes(alert.severity.toLowerCase())?alert.severity.toLowerCase():'low';
    heading.append(node('strong',alert.type),node('span',alert.severity,`severity-pill severity-${level}`));
    item.append(heading,node('div',`${alert.location} · ${alert.time}`),node('p',alert.description));
    if(alert.device_name)item.append(node('p',`Device: ${alert.device_name}`));
    const details=node('details');details.append(node('summary','Recommended action'),node('p','Review the live map and contact nearby response teams if this alert remains active.'));item.append(details);
    const form=node('form',undefined,'alert-dismiss-form form-actions');form.method='post';form.action=`/alerts/${alert.server_id}/dismiss/`;
    const csrf=node('input');csrf.type='hidden';csrf.name='csrfmiddlewaretoken';csrf.value=token;
    const button=node('button','Dismiss','button button-secondary');button.type='submit';form.append(csrf,button);item.append(form);items.append(item);
  }
  list.replaceChildren(items);
}
async function refresh() {
  if(refreshing||dismissing)return;
  refreshing=true;
  const epoch=generation;
  try{
    const response=await fetch('/alerts/feed/',{cache:'no-store',headers:{'Accept':'application/json'}});
    if(!response.ok||response.redirected)throw Error('Sign in again to refresh alerts.');
    const data=await response.json(),next=JSON.stringify(data.alerts);
    if(epoch!==generation)return;
    if(next!==signature){render(data.alerts);signature=next;}
    status.textContent='Alerts are up to date.';
  }catch(error){status.textContent='Unable to refresh alerts. Showing the last loaded alerts.';}
  finally{refreshing=false;}
}
list.addEventListener('submit',async e=>{
  const form=e.target.closest('.alert-dismiss-form');if(!form)return;
  e.preventDefault();if(dismissing)return;
  dismissing=true;generation++;const button=form.querySelector('button');button.disabled=true;
  try{
    const response=await fetch(form.action,{method:'POST',body:new FormData(form),headers:{'X-Requested-With':'XMLHttpRequest'}});
    if(!response.ok||response.redirected)throw Error('Unable to dismiss this alert. Refresh or sign in again.');
    signature=undefined;form.closest('li')?.remove();if(!list.querySelector('[data-alert-id]'))render([]);status.textContent='Alert dismissed.';
  }catch(error){status.textContent=error.message;return;}
  finally{dismissing=false;button.disabled=false;}
  await refresh();
});
document.getElementById('refresh-alerts').addEventListener('click',refresh);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
setInterval(()=>{if(!document.hidden)refresh();},5000);
refresh();
