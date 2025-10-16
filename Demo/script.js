document.addEventListener("DOMContentLoaded", function() {
  const form = document.getElementById("uploadForm");
  const loading = document.getElementById("loading");
  const resultBox = document.getElementById("result");
  const summaryBox = document.getElementById("summary");
  const categoryBox = document.getElementById("category");
  const topCandidatesList = document.getElementById("topCandidates");

  form.addEventListener("submit", async function(e) {
    e.preventDefault();

    const formData = new FormData(form);
    loading.style.display = "block";
    resultBox.style.display = "none";

    summaryBox.textContent = "";
    categoryBox.textContent = "";
    topCandidatesList.innerHTML = "";

    try {
      const response = await fetch("http://127.0.0.1:8000/process_pdf", {
        method: "POST",
        body: formData
      });

      if (!response.ok) {
        throw new Error("Kết nối thất bại: " + response.status);
      }

      const data = await response.json();
      loading.style.display = "none";
      resultBox.style.display = "block";

      if (data.status === "success") {
        summaryBox.textContent = data.summary || "(Không có tóm tắt)";
        categoryBox.textContent = data.category || "(Không xác định)";

        if (data.top_candidates && Array.isArray(data.top_candidates)) {
          data.top_candidates.forEach((item, i) => {
            const li = document.createElement("li");
            li.textContent = `${i + 1}. ${item.text || "(Không có nội dung)"}`;
            topCandidatesList.appendChild(li);
          });
        }
      } else {
        alert("❌ Lỗi xử lý: " + (data.message || "Không rõ"));
      }
    } catch (err) {
      loading.style.display = "none";
      alert("⚠️ Không thể kết nối tới Flask API. Hãy chắc rằng App_Run.py đang chạy!");
      console.error(err);
    }
  });
});
