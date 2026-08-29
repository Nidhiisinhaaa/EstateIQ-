// Live-polls the retrain job status endpoint every 2 seconds while a job is queued/running.

(function () {
  const jobId = window.ESTATEIQ_RETRAIN_JOB_ID;
  if (!jobId) return;

  const statusBlock = document.getElementById("job-status");
  const submitBtn = document.getElementById("retrain-submit");
  if (!statusBlock) return;

  const fields = {
    status: statusBlock.querySelector('[data-field="status"]'),
    started_at: statusBlock.querySelector('[data-field="started_at"]'),
    finished_at: statusBlock.querySelector('[data-field="finished_at"]'),
    log_tail: statusBlock.querySelector('[data-field="log_tail"]'),
  };

  function isTerminal(status) {
    return status === "success" || status === "failed";
  }

  function poll() {
    fetch(`${window.ESTATEIQ_RETRAIN_STATUS_URL_BASE}${jobId}/status/`)
      .then((res) => res.json())
      .then((data) => {
        fields.status.textContent = data.status;
        fields.started_at.textContent = data.started_at || "--";
        fields.finished_at.textContent = data.finished_at || "--";
        fields.log_tail.textContent = data.log_tail;
        fields.log_tail.scrollTop = fields.log_tail.scrollHeight;

        if (isTerminal(data.status)) {
          if (submitBtn) submitBtn.disabled = false;
        } else {
          if (submitBtn) submitBtn.disabled = true;
          setTimeout(poll, 2000);
        }
      })
      .catch(() => setTimeout(poll, 4000));
  }

  const initialStatus = statusBlock.dataset.status;
  if (!isTerminal(initialStatus)) {
    poll();
  }
})();
