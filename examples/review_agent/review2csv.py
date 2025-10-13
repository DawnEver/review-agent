from review_agent.review import review2csv

input_folder_path = './input'
# review_type = 'literature_review'

input_folder_path = r'C:\Users\linxu\OneDrive - The University of Nottingham\PEMC\251006-Ferrari_Future_Traction_PhD_Program\review\Companies\Ferrari\auto_models\web_pages\Elettrica'
# review_type = 'automotive_article'

output_folder_path = './output'

# Select review type by ID or name:
# 0 -> 'literature_review'
# 1 -> 'automotive_article'
review_type_id = 1  # change to 0 for literature review

review2csv(input_folder_path, output_folder_path, review_type_id=review_type_id)
