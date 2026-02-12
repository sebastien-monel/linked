//https://fullcalendar.io/docs/event-object

document.addEventListener('DOMContentLoaded', function() {
   var calendarEl = document.getElementById('calendar');
   var calendar = new FullCalendar.Calendar(calendarEl, {
     height: "100%",
     customButtons: {
         add_event: {
           text: 'add event',
           click: function() {
             //alert('clicked the custom button!');
             window.open("/event_creation");
           }
       }
     },
     nowIndicator: true,
     nextDayThreshold: '05:00:00',
     /*lang: 'fr',*/
     locale: 'fr',
     initialView: 'timeGridWeek',
     headerToolbar: {
        left: 'prev,next today add_event',
        center: 'title',
        right: 'multiMonthYear,dayGridMonth,timeGridWeek,timeGridDay,listDay'
      },
      events: '/events.json',
      /*
      eventDidMount: function(info) {
        var tooltip = new Tooltip(info.el, {
          title: info.event.extendedProps.description,
          placement: 'top',
          trigger: 'hover',
          container: 'body'
        });
      },*/
      eventClick: function(info) {
        info.jsEvent.preventDefault(); // don't let the browser navigate
        //url = "/event_details?type=eventClick&uid=" + encodeURIComponent(info.event.id) + "&title=" + encodeURIComponent(info.event.title);
        url = "/repository?type=eventClick&id=" + encodeURIComponent(info.event.id)
        window.open(url);
      },
      dateClick: function(info /*date, jsEvent, view*/) {
        info.jsEvent.preventDefault(); // don't let the browser navigate
        //alert('Clicked on: ' + info.dateStr /*date.toISOString() ... .format()*/ + ' from: ' + info.view.type);
        //url = "/event_details?start=" + encodeURIComponent(info.dateStr) + "&type=" + encodeURIComponent(info.view.type);
        url = "/event_creation?start=" + encodeURIComponent(info.dateStr) + "&type=" + encodeURIComponent(info.view.type);
        window.open(url);
      }
    },
  );
  setInterval(function(){calendar.refetchEvents();}, 5000);
  calendar.render();

});
