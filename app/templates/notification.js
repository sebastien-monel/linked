async function notification_check() {
  const response = await fetch("/notifications.json");
  
  if (!response.ok) {
    throw new Error(`Response status: ${response.status}`);
  }
  
  const notifications_json = await response.json();  
  const notifications_tab = [] ;
  
  for (const notification of notifications_json) {
      notifications_tab.push( new Notification("Brouillon :", {
        body: notification['body'], 
        tag : notification['tag']} 
      ))
  }
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

