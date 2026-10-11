// Every jQuery POST sends the session's CSRF token (see web/security.py).
// Run again once the page is parsed: some pages load another jQuery after
// this file, and that copy would not have the setting.
function sherlocCsrfSetup() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && window.jQuery) {
        jQuery.ajaxSetup({headers: {"X-CSRFToken": meta.content}});
    }
}
sherlocCsrfSetup();
document.addEventListener("DOMContentLoaded", sherlocCsrfSetup);

function delete_app(appid, e) {
    y = confirm(`Are you sure you want to delete the app  '${appid}'?"`);
    if (!y){return;}
    data = {'appid': appid, 'serial': serial, 'device': device};
    $.post('/delete/app/' + scanid, data=data).done(function (r){
        $('tr#' + appid).addClass('text-muted');
        $(e).removeClass('text-warning');
        $(e).addClass('text-success');
        $(e).html('&#10003;');
        $(e).prop('onclick', null).off('click');
        report_success(r);
    }).fail(function(){
        report_failure("Could not delete the app '" + appid + "'")
    })
}

function getScreenshot(buttonId, device, ser) { // ButtonId is the context which the screenshot was taken
    if (ser != "None" && ser != null) {
        var imageDiv = document.createElement('div');
        imageDiv.classList.add("form-screenshot");
        var loading = document.createElement('img')
        loading.src = "../../../webstatic/images/waiting.gif";
        imageDiv.innerHTML = loading.outerHTML;
        document.getElementById(buttonId).parentNode.insertBefore(imageDiv, document.getElementById(buttonId).nextSibling);
        fetch('/privacy/' + device + '/screenshot/' + buttonId + '/' + ser)
        .then(response => response.text())
        .then(data => {
            imageDiv.innerHTML = data;
            document.getElementById(buttonId).parentNode.insertBefore(imageDiv, document.getElementById(buttonId).nextSibling);
        })
        .catch(error => {
            imageDiv.innerHTML = "Error loading screenshot: " + error;
        });
        console.log("done")
    }
}
