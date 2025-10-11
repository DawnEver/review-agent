from review_agent.review import review2csv

input_folder_path = './input'
# review_type = 'literature_review'

input_folder_path = r'C:\Users\linxu\OneDrive - The University of Nottingham\PEMC\251006-Ferrari_Future_Traction_PhD_Program\review\Companies\Ferrari\auto_models\web_pages\Elettrica'
# review_type = 'automotive_article'

output_folder_path = './output'
review2csv(input_folder_path, output_folder_path)
