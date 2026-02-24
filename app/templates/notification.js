async function notification_check() {
  const response = await fetch("/notifications.json");
  
  if (!response.ok) {
    throw new Error(`Response status: ${response.status}`);
  }
  
  const notifications_json = await response.json();  
  const notifications_tab = [] ;
  
  for (const notification of notifications_json) {
    const notification_obj = new Notification("Brouillon :", {
        body: notification['body'], 
        tag : notification['tag']} 
      )
    notification_obj.onclick = click_notification
    notifications_tab.push( notification_obj )
  }
}

async function click_notification(event) {
  event.preventDefault(); // prevent the browser from focusing the Notification's tab
  window.open("/notification", "_blank");
}

Notification.requestPermission().then((status) => {
  //if (status === "denied") {
  //}
  
  //if (status === "default") {
    //Notification.requestPermission(location.reload(true))
  //} 
  
  if (status === "granted") {
    const interval = setInterval(notification_check , 1000)
  }
})

